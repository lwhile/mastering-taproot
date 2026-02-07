# Chapter 12: Silent Payments — Elliptic Curve Arithmetic and Address Privacy

## Why This Chapter Matters

The previous three chapters demonstrated three advanced application capabilities of Taproot:

- Chapter 9 (Ordinals): Witness space as a data container
- Chapter 10 (RGB): Script path commitments anchoring off-chain state
- Chapter 11 (Lightning Network): Key aggregation + script trees enabling privacy protocols

This chapter introduces Taproot's **fourth capability dimension** — **composability of elliptic curve arithmetic** and **output indistinguishability**.

In Chapter 5, when we introduced Schnorr signatures, we learned about elliptic curve linearity — the correspondence between point addition on public keys and scalar addition on private keys. At that time, it served key aggregation (MuSig2). Now, the same mathematical property underpins a completely different application: non-interactive privacy addresses.

Silent Payments (BIP352) solves one of Bitcoin's oldest user experience challenges: **how to safely reuse an address without interaction?**

Traditionally, receiving each payment requires generating a new address and sharing it with the sender. This is not only inconvenient but means any "public address" (such as a donation page) leads to address reuse, exposing the entire payment history.

Silent Payments lets the receiver publish a **static, reusable address**, yet each payment produces a **fresh, unlinkable Taproot output** on-chain.

It requires no consensus-layer changes — the generated outputs are standard P2TR outputs. All it needs is what Taproot already provides: **x-only public key format and a sufficiently large anonymity set**.

From an engineering perspective, this chapter addresses:

- Why address reuse is a privacy disaster
- Why previous approaches (BIP47 PayNym) fall short
- The cryptographic principles of Silent Payments: ECDH + point addition
- How to manually implement the complete send and scan flow in Python
- Why Silent Payments are inherently bound to Taproot
- The computational cost of receiver scanning and engineering trade-offs

If Lightning Network channels proved that "complex protocols should leave no more on-chain trace than simple payments," then Silent Payments prove that "address reuse should not come at the cost of privacy."

## The Problem: Address Reuse and Interactive Payments

### The Privacy Disaster of Address Reuse

Bitcoin's UTXO model naturally supports one-time addresses — every transaction can use a new receiving address. But in practice, many scenarios cannot avoid address reuse:

```
Scenario 1: Open-source project donation page
  "Please send donations to bc1q..."
  → All donors' transactions are linked to the same address
  → Anyone can see total donations and the source of each one

Scenario 2: Freelancer's payment QR code
  A business card with a single QR code
  → All clients pay to the same address
  → Client A can see Client B's payments

Scenario 3: Transfers between friends
  "Send me 0.01 BTC, my address is..."
  → If the same address receives all friends' transfers
  → Friends can see each other's payment records
```

**The core contradiction:**

- **Convenience** demands a fixed address, always ready to receive
- **Privacy** demands a different address for every receipt
- **Non-interactivity** means the receiver cannot generate a new address before each payment

### A Previous Attempt: BIP47 PayNym

BIP47 proposed "Reusable Payment Codes":

```
BIP47 Flow:
1. Bob publishes a payment code
2. When Alice wants to pay Bob, she first sends a "notification transaction" to Bob's notification address
3. The notification transaction's OP_RETURN contains Alice's public key information
4. Bob extracts Alice's public key from the notification transaction
5. From then on, Alice and Bob can use ECDH to derive unlimited one-time addresses
```

**BIP47's Problems:**

```
✗ Requires an on-chain notification transaction (extra fees and on-chain footprint)
✗ The notification transaction itself exposes Alice and Bob's link on-chain
✗ Each new sender requires a notification transaction
✗ Notification addresses can be identified by blockchain analysts
```

The notification transaction is like posting a note on a bulletin board saying "Alice is about to pay Bob" — even if the subsequent actual payments are private, that initial link has already been leaked.

## Silent Payments: Core Concepts

Silent Payments (BIP352, by Ruben Somsen and Josie Baker, 2023) eliminates the notification transaction, achieving **completely non-interactive** reusable addresses.

### One-Sentence Summary

**The sender uses their transaction input private key and the receiver's static public key to perform ECDH, deriving a one-time Taproot address without any interaction.**

### Core Flow

```
┌─────────────────────────────────────────────────────┐
│               Silent Payments Flow                    │
│                                                      │
│  1. Bob generates a Silent Payment address            │
│     Contains two public keys: B_scan and B_spend      │
│     Address format: sp1q... (117+ characters)         │
│                                                      │
│  2. Alice wants to pay Bob                            │
│     a. Alice selects UTXOs to spend (inputs),         │
│        obtains private key a                          │
│     b. Alice performs ECDH with a and B_scan           │
│        → shared secret                               │
│     c. Alice adds shared secret to B_spend             │
│        → one-time public key P                        │
│     d. Alice encodes P as a P2TR address, sends funds  │
│                                                      │
│  3. Bob scans the blockchain                          │
│     a. For every transaction with Taproot outputs      │
│     b. Extract input public key A                     │
│     c. Use b_scan and A for ECDH → re-derive P        │
│     d. Check if P matches any transaction output       │
│                                                      │
│  What the chain sees: An ordinary Taproot transfer     │
│  What the observer knows: Nothing                     │
└─────────────────────────────────────────────────────┘
```

### The Key Innovation

```
BIP47 (PayNym):     Notification tx (on-chain) → ECDH → Derive address
Silent Payments:    Transaction input pubkey → ECDH → Derive address
                    ↑
                    This information is already exposed when the tx is broadcast!
```

The elegance of Silent Payments lies in this: **the sender's public key doesn't need an extra notification transaction to be communicated, because it already exists in the transaction inputs**. Once a transaction is broadcast, the input public keys are naturally exposed, and the receiver can extract them from the chain to compute the shared secret.

## Cryptographic Foundations: ECDH and Point Addition

### ECDH (Elliptic Curve Diffie-Hellman)

ECDH is the mathematical core of Silent Payments. It allows two parties to establish a shared secret without direct communication:

```
Alice's key pair: (a, A), where A = a·G
Bob's key pair:   (b, B), where B = b·G

Alice computes: shared_secret = a·B = a·(b·G) = (a·b)·G
Bob computes:   shared_secret = b·A = b·(a·G) = (b·a)·G

Because EC multiplication is commutative: a·b = b·a
Therefore: a·B == b·A

Both parties arrive at the same shared secret, but external observers
can only see A and B — they cannot compute a·B from A and B
(this is the elliptic curve discrete logarithm problem).
```

### From Shared Secret to One-Time Address

The shared secret cannot be used directly as an address — using the same input and receiver public key would produce the same address every time. So BIP352 **hashes** the shared secret and uses it as a **point addition tweak**:

```
Simplified:
P = B_spend + hash(a·B_scan)·G

Full version (BIP352 v0):
input_hash = hash(outpoint_lowest || A_sum)
shared_secret = input_hash · a · B_scan
t_k = hash(shared_secret || k)
P_k = B_spend + t_k·G

Where:
  A_sum = sum of all input public keys participating in shared secret derivation
  outpoint_lowest = lexicographically smallest outpoint among all inputs (for uniqueness)
  k = output index (allows creating multiple Silent Payment outputs in one transaction)
```

**Why point addition instead of using the shared secret directly?**

If we directly used `hash(shared_secret)` as the new private key, only Alice could compute it — Bob wouldn't be able to spend. Through **point addition** `B_spend + t·G`, Bob can use `b_spend + t` as the corresponding private key to spend. This is the power of elliptic curve linearity — the exact same mathematical principle as Taproot's tweak mechanism.

### The Two-Key Split

BIP352 requires the receiver to generate **two** key pairs:

```
Scan key pair: (b_scan, B_scan)
  → Purpose: Used for ECDH to compute shared secrets
  → Security: Can be exported to light nodes / scanning servers
  → Exposure risk: Even if leaked, can only detect which transactions are yours,
                   cannot spend your funds

Spend key pair: (b_spend, B_spend)
  → Purpose: Generates the final one-time address, signs spends
  → Security: Must be kept strictly secret
  → Exposure risk: Leaked = funds stolen

BIP32 derivation paths:
  scan:  m/352'/coin_type'/account'/1'/0
  spend: m/352'/coin_type'/account'/0'/0
```

The benefit of this separation is enormous: Bob can hand his scan key to a server to scan for new payments, without worrying that the server can spend his money. This is critical for mobile wallets and light clients.

## Code Experiment 1: ECDH Shared Secret

This is the most fundamental experiment in this chapter. We manually implement ECDH in Python, verifying that sender and receiver can independently compute the same shared secret.

> **Note on code libraries**: This chapter's code directly uses the `coincurve` library
> to operate on elliptic curve primitives (scalar multiplication, point addition),
> rather than the `bitcoinutils` transaction-building library used in previous chapters.
> This is because Silent Payments' core logic operates at the cryptographic level,
> prior to transaction construction — we need to compute the address before we can build a transaction.

```python
import hashlib
from coincurve import PrivateKey, PublicKey

# ===== Bob: Receiver, generates Silent Payment key pairs =====
# In practice these keys derive from BIP32; here we generate directly

bob_scan_priv = PrivateKey(hashlib.sha256(b"bob_scan_secret").digest())
bob_spend_priv = PrivateKey(hashlib.sha256(b"bob_spend_secret").digest())

bob_scan_pub = bob_scan_priv.public_key
bob_spend_pub = bob_spend_priv.public_key

print("===== Bob's Silent Payment Keys =====")
print(f"B_scan:  {bob_scan_pub.format().hex()}")
print(f"B_spend: {bob_spend_pub.format().hex()}")

# ===== Alice: Sender, obtains key from the UTXO she's spending =====
alice_input_priv = PrivateKey(hashlib.sha256(b"alice_input_secret").digest())
alice_input_pub = alice_input_priv.public_key

print(f"\n===== Alice's Input Key =====")
print(f"A (input pubkey): {alice_input_pub.format().hex()}")

# ===== ECDH: Both parties independently compute shared secret =====
# Alice computes: a · B_scan
# Bob computes:   b_scan · A

# Method: elliptic curve scalar multiplication
alice_shared = alice_input_pub.multiply(bob_scan_priv.secret)  # simulates b_scan · A
bob_shared = bob_scan_pub.multiply(alice_input_priv.secret)    # simulates a · B_scan

# Due to ECDH symmetry, both should be equal:
# a · B_scan = a · (b_scan · G) = (a · b_scan) · G
# b_scan · A = b_scan · (a · G) = (b_scan · a) · G
# EC multiplication is commutative, so results are identical

print(f"\n===== ECDH Shared Secret =====")
print(f"Alice computes (a · B_scan):  {alice_shared.format().hex()}")
print(f"Bob computes   (b_scan · A):  {bob_shared.format().hex()}")
print(f"Shared secrets match: {alice_shared.format() == bob_shared.format()}")
```

**Key Observation:**
Alice and Bob never directly exchanged any secret information. Alice only knows Bob's public key (from the Silent Payment address), and Bob only knows Alice's public key (from the on-chain transaction input). Yet both can compute the same shared secret.

## Code Experiment 2: Deriving a One-Time Address from the Shared Secret

```python
# ===== Derive a Taproot one-time address from the shared secret =====

# Step 1: Perform a tagged hash on the shared secret
# BIP352 uses hash("BIP0352/SharedSecret" || shared_secret || k)

def tagged_hash(tag: str, data: bytes) -> bytes:
    """BIP340 style tagged hash"""
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()

shared_secret_bytes = bob_shared.format()  # 33-byte compressed pubkey format
k = 0  # First output

# t_k = hash("BIP0352/SharedSecret" || ser(shared_secret) || ser32(k))
t_k = tagged_hash(
    "BIP0352/SharedSecret",
    shared_secret_bytes + k.to_bytes(4, 'big')
)

print(f"===== Deriving One-Time Address =====")
print(f"Shared secret:  {shared_secret_bytes.hex()}")
print(f"Output index k: {k}")
print(f"Tweak t_k:      {t_k.hex()}")

# Step 2: Compute the one-time public key
# P = B_spend + t_k · G
from coincurve import PrivateKey as CPrivateKey

# t_k · G
tweak_point = CPrivateKey(t_k).public_key

# P = B_spend + t_k · G (elliptic curve point addition)
one_time_pubkey = PublicKey.combine_keys([bob_spend_pub, tweak_point])

# Extract x-only public key (strip prefix byte)
x_only = one_time_pubkey.format(compressed=True)[1:]

print(f"t_k · G:        {tweak_point.format().hex()}")
print(f"B_spend:        {bob_spend_pub.format().hex()}")
print(f"P (one-time):   {one_time_pubkey.format().hex()}")
print(f"x-only (32b):   {x_only.hex()}")

# Step 3: Encode as a Taproot address
# P is a standard Taproot output public key
# ScriptPubKey: OP_1 <32-byte x-only pubkey>
scriptpubkey = bytes([0x51, 0x20]) + x_only
print(f"\nScriptPubKey: {scriptpubkey.hex()}")
print(f"Format: OP_1 <32-byte-x-only-key>")
print(f"This is identical to any other Taproot output!")

# ===== Alice's side: her computation is exactly the same =====
# Alice uses her own computed shared secret to get the same t_k and P

alice_shared_bytes = alice_shared.format()
alice_t_k = tagged_hash(
    "BIP0352/SharedSecret",
    alice_shared_bytes + k.to_bytes(4, 'big')
)
alice_tweak_point = CPrivateKey(alice_t_k).public_key
alice_one_time_pubkey = PublicKey.combine_keys([bob_spend_pub, alice_tweak_point])

print(f"\n===== Verification: Alice and Bob derive the same address =====")
print(f"Alice derives: {alice_one_time_pubkey.format().hex()}")
print(f"Bob derives:   {one_time_pubkey.format().hex()}")
print(f"Match: {alice_one_time_pubkey.format() == one_time_pubkey.format()}")
```

## Code Experiment 3: How Bob Spends

Bob received funds, but what private key does he use to spend?

```python
# ===== Bob computes the spending private key =====
# One-time public key:  P = B_spend + t_k · G
# Corresponding privkey: p = b_spend + t_k
# Because: (b_spend + t_k) · G = b_spend·G + t_k·G = B_spend + t_k·G = P

import secrets

# Bob's spend private key (original)
b_spend_int = int.from_bytes(bob_spend_priv.secret, 'big')

# Tweak value t_k
t_k_int = int.from_bytes(t_k, 'big')

# One-time private key = b_spend + t_k (mod n)
SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
one_time_privkey_int = (b_spend_int + t_k_int) % SECP256K1_ORDER
one_time_privkey_bytes = one_time_privkey_int.to_bytes(32, 'big')

# Verify: public key derived from private key should == previously derived one-time pubkey
one_time_privkey = CPrivateKey(one_time_privkey_bytes)
derived_pubkey = one_time_privkey.public_key

print(f"===== Bob's Spending Key =====")
print(f"b_spend:        {bob_spend_priv.secret.hex()}")
print(f"t_k:            {t_k.hex()}")
print(f"b_spend + t_k:  {one_time_privkey_bytes.hex()}")
print(f"\nPublic key verification:")
print(f"From privkey:   {derived_pubkey.format().hex()}")
print(f"Previously:     {one_time_pubkey.format().hex()}")
print(f"Match: {derived_pubkey.format() == one_time_pubkey.format()}")

print(f"\n===== Mathematical Essence =====")
print(f"P = B_spend + t_k·G")
print(f"p = b_spend + t_k")
print(f"p·G = (b_spend + t_k)·G = B_spend + t_k·G = P ✓")
print(f"\nThis is the exact same math as Taproot's tweak!")
print(f"Taproot: output_key = internal_key + hash(internal_key || script_root)·G")
print(f"SP:      P          = B_spend      + hash(shared_secret || k)·G")
```

**Comparing with Taproot tweak:**

```
Taproot tweak:         P = Q + hash(Q || merkle_root) · G
Silent Payment tweak:  P = B_spend + hash(shared_secret || k) · G

The mathematical structure is identical:
  original_pubkey + hash(some_commitment) · G = tweaked_pubkey
  original_privkey + hash(some_commitment)     = tweaked_privkey
```

This is not a coincidence. Both Taproot and Silent Payments exploit elliptic curve **linearity**: if you know the private key for a public key, after tweaking the public key with point addition, the corresponding private key only needs scalar addition with the same tweak.

## Code Experiment 4: Receiver Scanning

This is Silent Payments' most critical engineering challenge. Bob doesn't know which transactions are for him — he must **check every transaction with Taproot outputs**.

```python
# ===== Simulating block scanning =====

import os

def simulate_scan():
    """Simulate Bob scanning transactions in a block"""
    
    # Bob's keys
    b_scan = bob_scan_priv
    B_spend = bob_spend_pub
    
    # ===== Simulate 5 transactions in a block =====
    # Only the 3rd one is Alice's Silent Payment to Bob
    
    transactions = []
    
    # Transaction 0: Ordinary Taproot payment (not for Bob)
    random_key_0 = PrivateKey(os.urandom(32))
    random_output_0 = PrivateKey(os.urandom(32)).public_key
    transactions.append({
        'txid': 'tx0',
        'input_pubkeys': [random_key_0.public_key],
        'taproot_outputs': [random_output_0.format(compressed=True)[1:]],  # x-only
    })
    
    # Transaction 1: Another ordinary transaction
    random_key_1 = PrivateKey(os.urandom(32))
    random_output_1 = PrivateKey(os.urandom(32)).public_key
    transactions.append({
        'txid': 'tx1',
        'input_pubkeys': [random_key_1.public_key],
        'taproot_outputs': [random_output_1.format(compressed=True)[1:]],
    })
    
    # Transaction 2: Alice's Silent Payment to Bob!
    alice_pub = alice_input_pub
    sp_output = one_time_pubkey.format(compressed=True)[1:]  # x-only
    transactions.append({
        'txid': 'tx2_alice_to_bob',
        'input_pubkeys': [alice_pub],
        'taproot_outputs': [sp_output],
    })
    
    # Transaction 3: Another ordinary transaction
    random_key_3 = PrivateKey(os.urandom(32))
    random_output_3 = PrivateKey(os.urandom(32)).public_key
    transactions.append({
        'txid': 'tx3',
        'input_pubkeys': [random_key_3.public_key],
        'taproot_outputs': [random_output_3.format(compressed=True)[1:]],
    })
    
    # Transaction 4: Another ordinary transaction
    random_key_4 = PrivateKey(os.urandom(32))
    random_output_4 = PrivateKey(os.urandom(32)).public_key
    transactions.append({
        'txid': 'tx4',
        'input_pubkeys': [random_key_4.public_key],
        'taproot_outputs': [random_output_4.format(compressed=True)[1:]],
    })
    
    # ===== Bob's scanning process =====
    print("===== Bob begins scanning the block =====")
    print(f"Block contains {len(transactions)} transactions")
    print()
    
    found_payments = []
    ecdh_count = 0
    
    for tx in transactions:
        if not tx['taproot_outputs']:
            print(f"  {tx['txid']}: No Taproot outputs, skipping")
            continue
        
        for input_pub in tx['input_pubkeys']:
            # Bob computes ECDH: b_scan · A
            ecdh_result = input_pub.multiply(b_scan.secret)
            ecdh_count += 1
            
            # Derive one-time public key
            shared_bytes = ecdh_result.format()
            k = 0
            t = tagged_hash(
                "BIP0352/SharedSecret",
                shared_bytes + k.to_bytes(4, 'big')
            )
            tweak_pub = CPrivateKey(t).public_key
            expected_output = PublicKey.combine_keys([B_spend, tweak_pub])
            expected_x_only = expected_output.format(compressed=True)[1:]
            
            # Check if it matches any Taproot output
            for output in tx['taproot_outputs']:
                if output == expected_x_only:
                    print(f"  ✓ {tx['txid']}: Silent Payment found!")
                    print(f"    Matching output: {output.hex()}")
                    found_payments.append({
                        'txid': tx['txid'],
                        'output': output,
                        'tweak': t,
                    })
                else:
                    pass  # No match, continue
    
    print(f"\n===== Scan Results =====")
    print(f"ECDH operations performed: {ecdh_count}")
    print(f"Silent Payments found: {len(found_payments)}")
    for p in found_payments:
        print(f"  Transaction: {p['txid']}")
        print(f"  Output: {p['output'].hex()}")

simulate_scan()
```

### The Computational Cost of Scanning

The simulation above illustrates the core challenge: Bob must perform at least one elliptic curve multiplication for **every transaction with Taproot outputs**.

```
Scanning cost analysis:

Assuming a block has 3,000 transactions:
  - About 40% have Taproot outputs ≈ 1,200 transactions
  - Each averages 1.5 inputs participating in ECDH
  - Bob needs: ~1,200 ECDH computations

Each ECDH = one elliptic curve scalar multiplication
  - Modern hardware: ~0.05ms per operation
  - Per block: ~60ms
  - Per day (144 blocks): ~8.6 seconds

Compared to BIP32 HD wallets:
  - BIP32 only needs to look up known addresses in the UTXO set
  - Essentially a hash table lookup, near-zero cost
  - Silent Payments scanning cost is orders of magnitude higher
```

**Optimization techniques:**

1. **input_hash + A_sum aggregation** (the most important optimization): BIP352 requires first summing all input public keys participating in ECDH into `A_sum = A_1 + A_2 + ... + A_n` (EC addition, very fast), then Bob only needs **one** ECDH: `shared_secret = input_hash · b_scan · A_sum`. This reduces EC multiplications per transaction from N to 1.
2. **BIP158 compact block filters**: Use filters to quickly exclude non-matching blocks
3. **Ignore dust outputs**: Skip outputs with negligible amounts
4. **Start height**: Only scan blocks after the wallet creation time
5. **Light client indexing**: Dedicated servers pre-compute `input_hash · A_sum` per transaction; Bob only needs to download 33 bytes per tx

## Code Experiment 5: Complete End-to-End Flow

Integrating all the above steps into a complete Silent Payment send → receive → spend flow.

```python
import hashlib
import os
from coincurve import PrivateKey, PublicKey

def tagged_hash(tag: str, data: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()

SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

print("=" * 70)
print("Silent Payment End-to-End Flow")
print("=" * 70)

# ===== 1. Bob: Generate Silent Payment address =====
print("\n[Step 1] Bob generates a Silent Payment address")

bob_scan_priv = PrivateKey(hashlib.sha256(b"bob_scan_key_demo").digest())
bob_spend_priv = PrivateKey(hashlib.sha256(b"bob_spend_key_demo").digest())
B_scan = bob_scan_priv.public_key
B_spend = bob_spend_priv.public_key

# Silent Payment address = bech32m(version || B_scan || B_spend)
# Simplified: display both public keys directly
print(f"  B_scan:  {B_scan.format().hex()}")
print(f"  B_spend: {B_spend.format().hex()}")
print(f"  Address format: sp1q<B_scan><B_spend> (bech32m encoded, 117+ chars)")

# ===== 2. Alice: Derive one-time address and send =====
print("\n[Step 2] Alice sends a Silent Payment to Bob")

# Alice selects UTXO to spend
alice_priv = PrivateKey(hashlib.sha256(b"alice_utxo_privkey_demo").digest())
A = alice_priv.public_key
print(f"  Alice input pubkey A: {A.format().hex()}")

# Alice computes ECDH shared secret: a · B_scan
shared_secret = B_scan.multiply(alice_priv.secret)
print(f"  Shared secret (a·B_scan): {shared_secret.format().hex()}")

# Alice computes tweak and derives one-time public key
k = 0
t_k = tagged_hash("BIP0352/SharedSecret",
                   shared_secret.format() + k.to_bytes(4, 'big'))
T_k = PrivateKey(t_k).public_key
P = PublicKey.combine_keys([B_spend, T_k])

x_only_P = P.format(compressed=True)[1:]  # x-only

print(f"  Tweak t_k: {t_k.hex()}")
print(f"  One-time pubkey P: {P.format().hex()}")
print(f"  P2TR ScriptPubKey: 5120{x_only_P.hex()}")
print(f"  → Alice sends 0.05 BTC to this Taproot address")

# ===== 3. Bob: Scan and discover the payment =====
print("\n[Step 3] Bob scans the blockchain, discovers Alice's payment")

# Bob extracts Alice's public key from transaction inputs
A_from_chain = A  # In practice, extracted from witness

# Bob computes ECDH: b_scan · A
bob_shared = A_from_chain.multiply(bob_scan_priv.secret)
print(f"  Bob's shared secret (b_scan·A): {bob_shared.format().hex()}")
print(f"  Matches Alice's: {bob_shared.format() == shared_secret.format()}")

# Bob derives the expected output public key
bob_t_k = tagged_hash("BIP0352/SharedSecret",
                       bob_shared.format() + k.to_bytes(4, 'big'))
bob_T_k = PrivateKey(bob_t_k).public_key
bob_expected_P = PublicKey.combine_keys([B_spend, bob_T_k])
bob_expected_x_only = bob_expected_P.format(compressed=True)[1:]

# Compare against on-chain output
match = (bob_expected_x_only == x_only_P)
print(f"  Expected output: {bob_expected_x_only.hex()}")
print(f"  On-chain output: {x_only_P.hex()}")
print(f"  ✓ Match! Bob discovered Alice's payment" if match else "  ✗ No match")

# ===== 4. Bob: Compute spending private key =====
print("\n[Step 4] Bob computes the spending private key")

b_spend_int = int.from_bytes(bob_spend_priv.secret, 'big')
t_k_int = int.from_bytes(bob_t_k, 'big')
p_int = (b_spend_int + t_k_int) % SECP256K1_ORDER
p_bytes = p_int.to_bytes(32, 'big')

# Verify
spend_key = PrivateKey(p_bytes)
verify_pub = spend_key.public_key
print(f"  Spending privkey p = b_spend + t_k: {p_bytes.hex()}")
print(f"  Verify p·G == P: {verify_pub.format() == P.format()}")
print(f"  → Bob can sign a Taproot key-path spend with this private key")

# ===== 5. On-chain visibility analysis =====
print(f"\n{'=' * 70}")
print("On-Chain Visibility Analysis")
print("=" * 70)
print(f"Transaction input:  Alice spends an ordinary UTXO (pubkey A exposed)")
print(f"Transaction output: A P2TR address (OP_1 <32 bytes>)")
print(f"")
print(f"Observer sees: An ordinary Taproot transfer")
print(f"Observer knows: Someone sent money to some Taproot address")
print(f"Observer does NOT know:")
print(f"  ✗ This is a Silent Payment")
print(f"  ✗ Who the receiver is")
print(f"  ✗ Other payments to the same receiver (address differs each time)")
print(f"  ✗ The receiver's Silent Payment address")
```

## Why Silent Payments Are Inherently Bound to Taproot

Silent Payments don't "happen to use Taproot" — they deeply depend on Taproot at multiple levels.

### Dependency 1: x-only Public Key Format

BIP352's address derivation directly operates on x-only (32-byte) public keys. Taproot (BIP341) defines the standardized handling of x-only public keys: always assume even y-coordinate. This eliminates the ambiguity issues of traditional compressed public keys (33 bytes, with 02/03 prefix).

```
Traditional public key: 02/03 + 32-byte x-coordinate
  → After ECDH, must handle y-coordinate parity
  → After point addition, must re-determine prefix

Taproot x-only public key: 32-byte x-coordinate
  → Uniformly assume even y
  → Cleaner mathematical operations
  → BIP340 Schnorr signatures directly support this
```

### Dependency 2: Anonymity Set

This is the most critical dependency. A Silent Payment output is a standard P2TR output — `OP_1 <32 bytes>`. Its privacy depends entirely on being **indistinguishable from all other Taproot outputs**.

```
If Silent Payments used P2WPKH:
  OP_0 <20-byte-hash>
  → P2WPKH outputs have a high on-chain share
  → But P2WPKH's anonymity set differs from Taproot's
  → And P2WPKH requires extra steps to generate address from public key

If Silent Payments use P2TR:
  OP_1 <32-byte-x-only-key>
  → Identical to all Taproot single-sig, multisig, and contract outputs
  → As Taproot adoption grows, the anonymity set grows
  → Lightning channels, Ordinals minting, ordinary transfers all contribute
```

This creates a **positive feedback loop**: all of Taproot's other applications (Lightning channels, Ordinals, RGB, etc.) increase the Taproot output anonymity set, thereby making Silent Payments more private.

### Dependency 3: Input Public Key Availability

BIP352 requires extracting public keys from transaction inputs for ECDH computation.
Not all input types can safely yield public keys — the specification explicitly lists supported input types:

| Input Type | Usable for SP | Reason |
|-----------|---------------|--------|
| P2TR (key path) | ✓ | Public key in scriptPubKey (previous output) |
| P2TR (script path) | ✓ | Public key in script |
| P2WPKH | ✓ | Public key in witness |
| P2SH-P2WPKH | ✓ | Public key in witness |
| P2PKH | ✗ | Public key in scriptSig has malleability risk |

Taproot inputs are the most natural pairing for Silent Payments — as more users adopt P2TR addresses, the ability to send Silent Payments naturally follows.

### Dependency 4: Same Mathematics as the Taproot Tweak

As discussed earlier, Silent Payment address derivation and Taproot output key derivation use the exact same mathematical structure: public key point addition + hash tweak. This means the same cryptographic toolkit serves both purposes.

## Privacy Scheme Comparison

Placing Silent Payments in the historical context of Bitcoin privacy schemes:

```
Scheme           Interactivity  On-chain Cost     Address Linking    Anonymity Set

Traditional HD   Interactive    No extra cost     Known addresses    Medium
                 (new addr each time)              trackable

BIP47 PayNym    Needs notif tx  Notif tx fee     Notif tx exposes   Medium
                                                  link

Silent Payments  Fully non-     Zero extra cost   Unlinkable         High (Taproot)
                 interactive                                        (positive feedback)
                 (uses existing inputs)
```

| Property | Traditional HD | BIP47 PayNym | Silent Payments |
|----------|---------------|-------------|-----------------|
| Receiver generates new address | Every time | Not needed | Not needed |
| Sender needs interaction | Must get new address | Must send notif tx | Not needed |
| On-chain overhead | None | Notification tx | None |
| Address reusable | No (reuse leaks) | Yes | Yes |
| Receiver computation cost | Low | Low | High (scanning) |
| Requires Taproot | No | No | Yes (core dependency) |
| Anonymity set | Depends on addr type | Medium | High (all Taproot) |

## Industry Progress: Silent Payments Are Already in Use

Silent Payments require no consensus-layer changes — it is a pure application-layer protocol. Multiple wallets have already implemented send and/or receive support:

### Supported Wallets

- **Cake Wallet**: Full send and receive support; one of the earliest wallets to implement Silent Payments
- **BitBox**: Supports sending to Silent Payment addresses
- **Silentium**: Experimental PWA light wallet with full send and receive support

### Infrastructure

- **BlindBit Oracle**: Provides pre-computed tweak indices for light clients, reducing scanning costs
- **Bitcoin Core PR #28122**: Implements BIP352 base cryptographic primitives (Sender/Recipient classes)

### Remaining Engineering Challenges

1. **Light client support**: How to enable mobile wallets to receive Silent Payments without downloading full blocks
2. **PSBT integration**: How to support Silent Payments in partially signed transactions (active discussion)
3. **Electrum server protocol**: Current Electrum protocol doesn't support the indexing Silent Payments requires
4. **CoinJoin compatibility**: Silent Payments in collaborative transactions require additional security measures

## Complete Taproot Advanced Application Landscape

With Silent Payments added, the book's Taproot advanced applications form a complete picture:

```
Taproot capability dimensions:

1. Witness space ────────────→ Ch 9  Ordinals: Data storage
                                No script size limits, witness becomes data container

2. Script path commitment ───→ Ch 10 RGB: Cryptographic anchoring
                                Tapret commits off-chain state, client-side validation

3. Schnorr linearity + ─────→ Ch 11 Lightning: Privacy protocol
   key aggregation + trees      MuSig2 cooperative signing, indistinguishable payments
                                Force close minimal exposure
                                PTLCs eliminate payment correlation

4. EC arithmetic + ──────────→ Ch 12 Silent Payments: Address privacy
   output indistinguishability   ECDH non-interactive shared secret
                                Point addition derives one-time addresses
                                Taproot anonymity set provides cover
```

| Chapter | Application | Taproot Capability | Core Breakthrough |
|---------|------------|-------------------|-------------------|
| Ch 9 | Ordinals | Witness space | Witness becomes general-purpose data container |
| Ch 10 | RGB | Script path commitment | Cryptographic notary for off-chain computation |
| Ch 11 | Lightning | Key aggregation + script trees | Complex protocols indistinguishable from simple payments |
| Ch 12 | Silent Payments | EC arithmetic + anonymity set | Static addresses without sacrificing privacy |

**The common theme across all four applications**: Taproot's design makes all operations on Bitcoin — no matter how complex — look like ordinary Taproot single-sig payments on-chain. Ordinals leverages witness space; RGB leverages script path commitments; Lightning leverages key aggregation; Silent Payments leverages the anonymity set.

**The positive feedback between them**: Every application's adoption increases the total number of Taproot outputs, thereby growing the anonymity set for all other applications. Lightning channel cooperative closes, Ordinals minting transactions, RGB state transitions, Silent Payment one-time addresses — they all appear on-chain as `OP_1 <32 bytes>`, serving as cover for each other.

## Exercises

### Exercise 1: Manual ECDH Implementation

1. Use the `coincurve` library to generate two key pairs (simulating Alice and Bob)
2. Compute the ECDH shared secret from both sides
3. Verify both parties get the same result
4. Try computing with a third party's (Eve's) key — confirm they cannot obtain the same secret

### Exercise 2: Derive Multiple One-Time Addresses

1. Using the same ECDH shared secret, derive multiple addresses by varying the index k (0, 1, 2, ...)
2. Verify each address is different
3. Verify Bob can compute the corresponding spending private key for each address
4. Think: Why is k needed? What if Alice wants to send two payments to Bob in the same transaction?

### Exercise 3: Simulate Block Scanning

1. Generate 100 simulated transactions, with 3 being Silent Payments to Bob
2. Implement Bob's scanning logic to find all 3
3. Record how long scanning takes
4. Compare: How long would checking 100 transactions take with a BIP32 HD wallet?

### Exercise 4: Identify Silent Payments on mempool.space

1. Visit mempool.space and find several Taproot transactions
2. Answer: Can you tell which ones are Silent Payments and which are ordinary transfers?
3. Why not? This is precisely the design goal of Silent Payments

### Exercise 5: Label Mechanism

1. Implement BIP352's Label feature: `B_m = B_spend + hash(b_scan || m)·G`
2. Generate 3 different labeled addresses for the same receiver
3. Verify Bob can distinguish which label received a payment during scanning
4. Think: Can an external observer tell these labeled addresses belong to the same entity?

> **Hint**: Labels create different SP addresses (`sp1q...`), but they share the same `B_scan`.
> If someone obtains multiple labeled SP addresses from you, they can link them by comparing `B_scan`.
> However, the on-chain one-time Taproot outputs remain unlinkable — Labels affect
> **address linkability**, not **on-chain output linkability**. Labels' core purpose is internal
> organization — similar to assigning different "sub-addresses" for different clients or purposes.

### Exercise 6: Compare Taproot Tweak and Silent Payment Tweak

1. Build a Taproot output with a script path, recording the output_key computation process
2. Build a Silent Payment output, recording the one-time public key computation process
3. Compare the two tweak formulas side by side
4. Answer: If you understood Taproot's tweak, have you already understood Silent Payment's core?

## Engineering Summary: Taproot as Privacy Infrastructure

### Core Principles Demonstrated by Silent Payments

1. **ECDH non-interactive shared secret**: Leverages public keys already exposed in transaction inputs, no extra communication needed
2. **Elliptic curve point addition**: Same mathematical structure as Taproot tweak, enabling key adjustment
3. **Two-key separation**: Scan key and spend key separation supports light client delegated scanning
4. **Taproot anonymity set**: All Taproot outputs serve as cover for each other, positive feedback loop

### Complete Book Taproot Technology Summary

From Chapter 5's Schnorr signatures to this chapter's Silent Payments, Taproot's technology stack can be summarized as the following core capabilities:

```
Schnorr Signatures (BIP340)
├── Linearity → Key aggregation (MuSig2) → Lightning channel key-path
├── Adaptor signatures → PTLC → Lightning cross-hop privacy
└── x-only public keys → Silent Payments address format simplification

Taproot (BIP341)
├── Key Path → Cooperative spending without revealing scripts → Lightning cooperative close
├── Script Path → Minimal script exposure → Lightning force close
├── Script Path commitment → Tapret → RGB state anchoring
├── Witness space → Inscriptions → Ordinals
└── P2TR output uniformity → Anonymity set → Silent Payments cover

Elliptic Curve Arithmetic
├── ECDH → Non-interactive shared secret → Silent Payments address derivation
├── Point addition (P + t·G) → Taproot tweak == SP tweak → Key adjustment
└── Scalar addition (p + t) → Corresponding privkey adjustment → Spendability
```

### Design Philosophy

Looking back across the entire book, Taproot's four advanced applications all follow the same design philosophy:

> **Make all operations look the same on-chain.**

- Ordinals: Inscription transactions look like ordinary Taproot transactions
- RGB: State transition transactions look like ordinary Taproot transactions
- Lightning Network: Channel opens and closes look like ordinary Taproot transactions
- Silent Payments: Private receipts look like ordinary Taproot transactions

This is not a coincidence in each application's design — it is the fundamental design intent of Taproot as a protocol upgrade.

## Conclusion

Silent Payments demonstrate Taproot's fourth capability dimension — **composability of elliptic curve arithmetic and output indistinguishability**.

1. **Non-interactive ECDH**: Leverages known public keys from transaction inputs, eliminating the need for notification transactions
2. **Point addition derivation**: Same mathematics as Taproot tweak, producing a different one-time address for each payment
3. **Taproot anonymity set**: Silent Payment outputs are indistinguishable from all P2TR outputs
4. **Two-key separation**: Scan key can be safely delegated, spend key strictly secret
5. **Positive feedback loop**: All other Taproot applications grow the anonymity set, in turn strengthening Silent Payments privacy

If Ordinals proved that Taproot's witness space can store arbitrary data,
RGB proved that Taproot's script path can anchor off-chain state,
Lightning Network proved that Taproot's key aggregation can hide complex protocols,
then Silent Payments prove that Taproot's elliptic curve arithmetic can make **a single unchanging address produce unlimited unlinkable on-chain payments**.

Four advanced application chapters, four Taproot capability dimensions, one unified theme:

**Complex operations on Bitcoin should leave no complex traces on-chain.**

Taproot makes this vision a reality.
