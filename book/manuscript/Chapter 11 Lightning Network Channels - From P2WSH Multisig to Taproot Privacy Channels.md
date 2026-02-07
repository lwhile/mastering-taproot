# Chapter 11: Lightning Network Channels — From P2WSH Multisig to Taproot Privacy Channels

## Why This Chapter Matters

The Lightning Network is one of Taproot's **original design motivations**.

Chapter 9 showed how Taproot's witness can serve as a data layer (Ordinals). Chapter 10 showed how Taproot's commitment capabilities can anchor off-chain contract state (RGB). This chapter returns to Taproot's core design goal: **making complex multi-party contracts look identical to ordinary payments on-chain**.

Lightning Network payment channels are the perfect embodiment of this design philosophy:

- Two participants lock funds into a jointly controlled output
- When cooperating (the vast majority of cases), both parties co-sign, and a single ordinary transaction closes the channel
- Only in disputes (rare cases) does complex script logic need to be revealed

From an engineering perspective, this chapter addresses:

- P2WSH's position in the Bitcoin address type spectrum — completing the last major address type we haven't covered
- How traditional Lightning channels use P2WSH 2-of-2 multisig to lock funds
- How Taproot channel **funding outputs** achieve pure key-path locking through MuSig2 + BIP86
- How Taproot channel **commitment transactions** use script trees for dispute resolution logic
- The on-chain differences between cooperative closes (key path) and force closes (script path)
- How the HTLC-to-PTLC evolution further unlocks the potential of Schnorr signatures

If Ordinals and RGB are Taproot's "unexpected harvests,"
then Lightning Network channels are Taproot's "original design intent."

## Lightning Network Fundamentals: The Minimal Payment Channel Model

Before diving into Taproot channels, we need to understand the core model of Lightning Network payment channels.

### What Is a Payment Channel

A payment channel allows two parties to conduct unlimited transactions **off-chain**, requiring only **two on-chain transactions**:

```
On-chain Transaction 1: Open Channel (Funding Transaction)
  └── Lock funds into a jointly controlled output (funding output)

Off-chain: Unlimited state updates
  └── Alice and Bob exchange signed commitment transactions off-chain
  └── Each update represents a reallocation of channel balances

On-chain Transaction 2: Close Channel (Closing Transaction)
  └── Distribute final balances to both parties
```

### Channel Lifecycle

```
┌─────────────────────────────────────────────────────┐
│                  Channel Lifecycle                    │
│                                                      │
│  1. Open Channel                                     │
│     Alice + Bob → Funding Transaction (on-chain)     │
│     Output: funding output (jointly controlled)      │
│                                                      │
│  2. Use Channel                                      │
│     Alice ←→ Bob: Exchange signed commitments        │
│     State #1: Alice=7, Bob=3                         │
│     State #2: Alice=5, Bob=5                         │
│     State #3: Alice=2, Bob=8                         │
│     ...                                              │
│                                                      │
│  3. Close Channel                                    │
│     Option A: Cooperative close — both sign to       │
│               spend the funding output               │
│     Option B: Force close — one party broadcasts     │
│               the latest commitment transaction      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

This chapter focuses on three key structures: the **funding output**,
the **commitment transaction**, and the **closing transaction**.
These are precisely where Taproot brings revolutionary improvements.

## The Last Piece of the Bitcoin Address Type Puzzle: P2WSH

Before we formally discuss Lightning channels, let's fill an important knowledge gap.

Reviewing the address type progression across the book:

```
Single-key path:
  Ch 2  P2PKH   → Ch 4  P2WPKH  → Ch 5  P2TR (key path)
  OP_DUP OP_HASH160    OP_0 <20 bytes>    OP_1 <32 bytes>

Script path:
  Ch 3  P2SH    → ???  P2WSH   → Ch 5  P2TR (script path)
  OP_HASH160 <20 bytes>  OP_0 <32 bytes>    OP_1 <32 bytes>
```

P2WSH (Pay-to-Witness-Script-Hash) is the missing link in the script path.
It is the SegWit upgrade of P2SH — placing the script hash into a witness program,
perfectly symmetric with what P2WPKH does for P2PKH:

| Address Type | ScriptPubKey Format | Essence | Chapter |
|-------------|---------------------|---------|---------|
| P2PKH | `OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG` | Pay to public key hash | Ch 2 |
| P2SH | `OP_HASH160 <hash> OP_EQUAL` | Pay to script hash | Ch 3 |
| P2WPKH | `OP_0 <20-byte-pubkey-hash>` | SegWit version of P2PKH | Ch 4 |
| **P2WSH** | **`OP_0 <32-byte-script-hash>`** | **SegWit version of P2SH** | **This chapter** |
| P2TR | `OP_1 <32-byte-output-key>` | Taproot (unifies both paths) | Ch 5+ |

P2TR ultimately unifies the single-key path and script path into a single address format —
this is the essence of Taproot's "payment uniformity." This chapter introduces P2WSH
through the real-world use case of Lightning channels, naturally completing the spectrum.

> **SegWit Backward Compatibility Note**: SegWit succeeded as a soft fork because
> old nodes seeing `OP_0 <hash>` treat it as an "anyone-can-spend" output
> (the top of stack is a non-zero hash value = true). Old nodes don't reject blocks
> containing such transactions, but new nodes recognize the `OP_0` version number
> and additionally verify the signatures in witness data.
> During early SegWit adoption, there was also a **P2SH-wrapped SegWit** approach
> (e.g., P2SH-P2WPKH), enabling older wallets that couldn't send to bech32 addresses
> to still send funds to SegWit outputs.
> Taproot uses `OP_1` as its version number, following the same backward-compatible logic.

## Traditional Lightning Channels: P2WSH 2-of-2 Multisig

### The Funding Output Script

Traditional Lightning channels use P2WSH (Pay-to-Witness-Script-Hash) to wrap a 2-of-2 multisig script:

```
Witness Script (redeem script):
  OP_2 <alice_pubkey> <bob_pubkey> OP_2 OP_CHECKMULTISIG

ScriptPubKey (visible on-chain):
  OP_0 <32-byte SHA256(witness_script)>
```

**On-chain visibility problems:**

1. **When opening**: Observers see `OP_0 <32-byte hash>`, identifying it as a P2WSH output. While the specific script content is hidden, they can infer it may be a multisig or Lightning channel.

2. **When closing**: The witness exposes two signatures and the complete 2-of-2 script:

```
Witness (data exposed during cooperative close):
  <> (empty element, legacy CHECKMULTISIG bug)
  <alice_signature> (71-72 bytes, DER encoded)
  <bob_signature>   (71-72 bytes, DER encoded)
  <witness_script>  (OP_2 <pk_a> <pk_b> OP_2 OP_CHECKMULTISIG, ~105 bytes)
  
Total: ~249 bytes
```

Everyone can see on-chain: this is a 2-of-2 multisig, most likely a Lightning Network channel.

### Code: Building a Traditional P2WSH Channel Funding Lock

```python
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2wshAddress
from bitcoinutils.script import Script

setup('testnet')

# ===== Alice and Bob's keys =====
alice_priv = PrivateKey('cT3tJP7BjwL25nQ9rHQuSCLugr3Vs5XfFKsTs7j5gHDgULyMmm1y')
bob_priv = PrivateKey('cNxX8M7XU8VNa5ofd8yk1eiKxmVUce6qn4d2Priv89dTLEP5GkzJ')

alice_pub = alice_priv.get_public_key()
bob_pub = bob_priv.get_public_key()

print(f"Alice pubkey: {alice_pub.to_hex()}")
print(f"Bob pubkey:   {bob_pub.to_hex()}")

# ===== 2-of-2 multisig witness script =====
funding_witness_script = Script([
    'OP_2',
    alice_pub.to_hex(),
    bob_pub.to_hex(),
    'OP_2',
    'OP_CHECKMULTISIG'
])

print(f"\nWitness Script: {funding_witness_script.to_hex()}")
print(f"Script length: {len(bytes.fromhex(funding_witness_script.to_hex()))} bytes")

# ===== P2WSH address =====
p2wsh_address = P2wshAddress.from_script(funding_witness_script)

print(f"\nTraditional channel funding address (P2WSH): {p2wsh_address.to_string()}")
print(f"ScriptPubKey: {p2wsh_address.to_script_pub_key().to_hex()}")
print(f"Format: OP_0 <32-byte-witness-script-hash>")

# ===== On-chain visibility analysis =====
print(f"\n=== On-Chain Visibility ===")
print(f"Observer sees: OP_0 + 32-byte hash")
print(f"Observer knows: This is a P2WSH output")
print(f"Observer infers: Likely multisig / Lightning channel")
```

## Taproot Lightning Channels: MuSig2 and BIP86 Fund Locking

### Core Architecture: Separating Funding Output from Commitment Transaction

Taproot channels use Taproot at two distinct levels, **with completely different structures**:

```
Level 1: Funding Output (fund locking)
  ├── Internal key: MuSig2(Alice, Bob) aggregate key
  ├── BIP86 tweak (no script path, provable)
  └── Can only be spent via key path (cooperative MuSig2 signature)

Level 2: Commitment Transaction Outputs
  ├── to_local output: has script tree (revocation + delayed spending)
  ├── to_remote output: has script tree (1-block CSV)
  └── HTLC outputs: have script trees (preimage/timeout/revocation)
```

**This is a critical distinction**: The funding output is pure key-path (BIP86, no script tree),
while the commitment transaction outputs use script trees for dispute resolution logic.

### MuSig2 Key Aggregation

MuSig2 (BIP 327) allows multiple parties to aggregate their public keys into one:

```
MuSig2 Protocol:
  1. KeyAgg:         Deterministic key aggregation (with coefficients, prevents rogue-key attacks)
  2. NonceGen:       Each party generates random nonces
  3. NonceAgg:       Aggregate nonces
  4. PartialSign:    Each party generates partial signatures
  5. PartialSigAgg:  Combine into a single complete Schnorr signature

Result: External observers see only an ordinary 32-byte public key and a 64-byte signature
        They cannot tell this was produced by two (or more) cooperating parties
```

**Code Demo (Conceptual Key Aggregation):**

```python
# ===== MuSig2 Key Aggregation Demo =====
#
# Important notes:
# 1. Real MuSig2 KeyAgg includes key coefficients (prevents rogue-key attacks)
# 2. Here we use simplified elliptic curve point addition to demonstrate the concept
# 3. The complete MuSig2 signing flow (nonce exchange, partial signatures) is not
#    demonstrated in this chapter
#    Reference: BIP 327 reference implementation (https://github.com/bitcoin/bips/tree/master/bip-0327)

from coincurve import PublicKey as CPublicKey

# Get compressed raw public keys
alice_raw = CPublicKey(bytes.fromhex(alice_pub.to_hex()))
bob_raw = CPublicKey(bytes.fromhex(bob_pub.to_hex()))

# Elliptic curve point addition (simplified KeyAgg)
combined_raw = CPublicKey.combine_keys([alice_raw, bob_raw])
combined_hex = combined_raw.format(compressed=True).hex()

print(f"Alice pubkey:          {alice_pub.to_hex()}")
print(f"Bob pubkey:            {bob_pub.to_hex()}")
print(f"Aggregate key (comp):  {combined_hex}")
print(f"Aggregate key (x-only): {combined_hex[2:]}")  # Remove 02/03 prefix
print(f"\nExternal observers see only an ordinary 32-byte public key")
print(f"They cannot tell it was aggregated from two parties' keys")
```

> **MuSig2 Signing Limitation Note**: This chapter's code demonstrates the concept
> of key aggregation (elliptic curve point addition), but **does not demonstrate
> the complete MuSig2 signing flow** (nonce exchange, partial signatures, signature aggregation).
> MuSig2 signing is a multi-round interactive protocol requiring both parties to be online —
> this goes beyond what a single-machine Python script can demonstrate.
> In subsequent key-path signing demos, we use Alice's single key as a simplified stand-in
> to show the on-chain witness structure differences. For complete MuSig2 signing implementations,
> refer to the BIP 327 reference implementation or `@cmdcode/musig2` (TypeScript).

### Funding Output: BIP86 Key-Only Path

The funding output uses a **BIP86 tweak** — meaning the Taproot output **provably has no script path**:

```
Funding Output structure:
  Internal key: P_agg = MuSig2(P_alice, P_bob)
  BIP86 tweak: Q = P_agg + H_taptweak(P_agg) * G
  (Note: tweak uses only the internal key, no merkle root)

  ScriptPubKey: OP_1 <Q>
  
  Spending: Key path only (MuSig2 aggregate signature)
  No script path (BIP86 proves this)
```

**Why no script path?**

The funding output's sole purpose is to lock funds, ensuring both parties must cooperate to spend.
All dispute resolution logic (revocation, timelocks, HTLCs) resides in the
**commitment transaction outputs**, not in the funding output. The BIP86 tweak allows
channel partners to prove to the network that this output truly has no hidden script path.

### Code: Building a Taproot Channel Funding Output

```python
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey
from bitcoinutils.script import Script
from coincurve import PublicKey as CPublicKey

setup('testnet')

# Alice and Bob's keys
alice_priv = PrivateKey('cT3tJP7BjwL25nQ9rHQuSCLugr3Vs5XfFKsTs7j5gHDgULyMmm1y')
bob_priv = PrivateKey('cNxX8M7XU8VNa5ofd8yk1eiKxmVUce6qn4d2Priv89dTLEP5GkzJ')
alice_pub = alice_priv.get_public_key()
bob_pub = bob_priv.get_public_key()

# ===== Key aggregation (simplified KeyAgg) =====
alice_raw = CPublicKey(bytes.fromhex(alice_pub.to_hex()))
bob_raw = CPublicKey(bytes.fromhex(bob_pub.to_hex()))
combined_raw = CPublicKey.combine_keys([alice_raw, bob_raw])
combined_hex = combined_raw.format(compressed=True).hex()
combined_pub = PublicKey(combined_hex)

# ===== BIP86 Taproot address (no script tree) =====
# get_taproot_address() without script tree argument = BIP86 tweak
funding_address = combined_pub.get_taproot_address()

print(f"Taproot channel funding address: {funding_address.to_string()}")
print(f"ScriptPubKey: {funding_address.to_script_pub_key().to_hex()}")
print(f"Format: OP_1 <32-byte-output-key>")
print(f"Script path: None (BIP86 proven)")

# ===== On-chain visibility analysis =====
print(f"\n=== On-Chain Visibility ===")
print(f"Observer sees: OP_1 + 32-byte public key")
print(f"Observer knows: This is a Taproot address")
print(f"Observer infers: Could be a regular payment, multisig, channel... indistinguishable")
```

## On-Chain Comparison: Two Approaches to Fund Locking

### ScriptPubKey Comparison

```python
# ===== Comparison =====
print("=" * 70)
print("Two Funding Output Approaches Compared")
print("=" * 70)

print(f"\n[P2WSH Approach (Traditional Lightning Channel)]")
print(f"Address:        {p2wsh_address.to_string()}")
print(f"ScriptPubKey:   {p2wsh_address.to_script_pub_key().to_hex()}")
print(f"Format:         OP_0 <32-byte-hash>")
print(f"Version:        SegWit v0")
print(f"Script path:    Yes (2-of-2 multisig exposed when spent)")

print(f"\n[Taproot Approach (Taproot Lightning Channel)]")
print(f"Address:        {funding_address.to_string()}")
print(f"ScriptPubKey:   {funding_address.to_script_pub_key().to_hex()}")
print(f"Format:         OP_1 <32-byte-key>")
print(f"Version:        SegWit v1 (Taproot)")
print(f"Script path:    None (BIP86 proves no hidden scripts)")

print(f"\n[Key Difference]")
print(f"P2WSH:   OP_0 prefix → observer knows it's a witness script hash")
print(f"Taproot: OP_1 prefix → identical to all other Taproot addresses, purpose indistinguishable")
```

### Cooperative Close Witness Comparison

Cooperative close is the **most common channel closing method** (over 90% of channels close cooperatively),
making the privacy and efficiency gains in this scenario highly significant.

A cooperative close directly spends the funding output — after both parties agree on the final balance allocation,
they sign a new transaction spending the funding output, distributing funds to each party.

```python
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.utils import to_satoshis

# ===== Scenario: Channel has 100,000 sats, final state Alice=60000, Bob=39700 =====
funding_txid = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
funding_amount = 100000
fee = 300

# =============================================
# Approach A: P2WSH Cooperative Close
# =============================================
p2wsh_tx = Transaction(
    [TxInput(funding_txid, 0)],
    [
        TxOutput(60000, alice_pub.get_segwit_address().to_script_pub_key()),
        TxOutput(39700, bob_pub.get_segwit_address().to_script_pub_key()),
    ],
    has_segwit=True
)

# Both parties sign independently
alice_sig = alice_priv.sign_segwit_input(
    p2wsh_tx, 0, funding_witness_script, to_satoshis(funding_amount / 100000000)
)
bob_sig = bob_priv.sign_segwit_input(
    p2wsh_tx, 0, funding_witness_script, to_satoshis(funding_amount / 100000000)
)

# P2WSH Witness: [empty, sig_alice, sig_bob, witness_script]
p2wsh_tx.witnesses.append(TxWitnessInput([
    '', alice_sig, bob_sig, funding_witness_script.to_hex()
]))

# =============================================
# Approach B: Taproot Cooperative Close (Key Path)
# =============================================
taproot_tx = Transaction(
    [TxInput(funding_txid, 0)],
    [
        TxOutput(60000, alice_pub.get_taproot_address().to_script_pub_key()),
        TxOutput(39700, bob_pub.get_taproot_address().to_script_pub_key()),
    ],
    has_segwit=True
)

# Key Path signature
# Production: MuSig2 aggregate signature (both parties contribute partial signatures, combined into one)
# Demo: Using Alice's key (MuSig2 signing requires multi-round interaction, cannot be demoed on a single machine)
taproot_sig = alice_priv.sign_taproot_input(
    taproot_tx, 0,
    [funding_address.to_script_pub_key()],
    [funding_amount],
    script_path=False  # Key Path
)

# Taproot Key Path Witness: [single signature]
taproot_tx.witnesses.append(TxWitnessInput([taproot_sig]))

# =============================================
# Comparison Summary
# =============================================
print("=" * 70)
print("Cooperative Close Witness Comparison")
print("=" * 70)
print(f"                      P2WSH            Taproot")
print(f"  Witness elements    4                1")
print(f"  Signatures          2 (DER)          1 (Schnorr)")
print(f"  Script exposed      Yes (2-of-2)     No")
print(f"  Witness size        ~249 bytes       64 bytes")
print(f"  Identifiable        Yes              No")
print(f"  Fee savings         Baseline         ~74% savings")
```

> **Sighash Note**: Taproot channels uniformly use `SIGHASH_DEFAULT` (0x00),
> functionally equivalent to `SIGHASH_ALL`, but the signature is 64 bytes (not 65),
> because the sighash byte is omitted when at its default value. This saves an additional byte.

## Commitment Transactions: The Channel's Off-Chain Heartbeat

### What Are Commitment Transactions

The funding output locks the funds, but balance changes within the channel are expressed through
**commitment transactions**. Each time Alice and Bob update the channel state off-chain,
they exchange newly signed commitment transactions.

```
Commitment Transaction's role:
  Input: Spends the funding output (requires MuSig2 signature)
  Outputs: Distribute channel balance
    ├── to_local:  Holder's own funds (with delay + revocation conditions)
    ├── to_remote: Counterparty's funds
    ├── HTLC outputs: In-flight payments (if any)
    └── Anchor outputs: For CPFP fee bumping
```

**Key Design: Asymmetric Commitment Transactions**

The commitment transaction Alice holds and the one Bob holds have **different structures**.
This is the core of the Lightning Network security model:

```
Alice's version:                     Bob's version:
  to_local: Alice's funds              to_local: Bob's funds
    (Alice must wait,                    (Bob must wait,
     Bob can revoke)                      Alice can revoke)
  to_remote: Bob's funds               to_remote: Alice's funds
    (Bob can spend immediately)          (Alice can spend immediately)
```

In each party's version, their own funds (to_local) have a delay,
while the counterparty's funds (to_remote) can be spent immediately.
The delay's purpose is to **give the counterparty time to detect cheating and execute punishment**.

### Taproot Structure of Commitment Transaction Outputs

This is the most elegant design in Taproot channels. Each output type uses a different Taproot strategy:

```
Commitment Transaction (Bob's version):

├── Output 0: to_local (Bob's funds)
│   ├── Internal Key: NUMS point (unspendable pubkey, forces script path)
│   └── Script Tree:
│       ├── Leaf 1: Revocation path — Alice can immediately seize funds (if Bob cheats)
│       │   <local_delay_key> OP_DROP <revocation_key> OP_CHECKSIG
│       └── Leaf 2: Delayed path — Bob waits N blocks then spends
│           <bob_delayed_key> OP_CHECKSIGVERIFY <delay> OP_CSV OP_DROP
│
├── Output 1: to_remote (Alice's funds)
│   ├── Internal Key: NUMS point
│   └── Script Tree:
│       └── Leaf: <alice_key> OP_CHECKSIGVERIFY 1 OP_CSV OP_DROP
│           (Alice waits 1 block confirmation, satisfying CPFP carve-out rule)
│
├── Output 2: Offered HTLC (in-flight payment Bob offered)
│   ├── Internal Key: revocation_key (key path = cheating punishment)
│   └── Script Tree:
│       ├── Leaf: Success — counterparty reveals preimage to claim
│       └── Leaf: Timeout — Bob reclaims after timeout
│
└── Output 3: Accepted HTLC (in-flight payment Bob received)
    ├── Internal Key: revocation_key
    └── Script Tree:
        ├── Leaf: Success — Bob reveals preimage to claim
        └── Leaf: Timeout — counterparty reclaims after timeout
```

**Design Highlights:**

- **Funding output** uses BIP86 (pure key path), maximizing privacy
- **to_local / to_remote** use NUMS point as internal key (forcing script path), ensuring timelock and revocation logic is enforced
- **HTLC outputs** use revocation key as internal key, making **revocation (cheating punishment) take the most efficient key path** (64-byte signature), while normal preimage/timeout flows use script path

> **NUMS Point (Nothing Up My Sleeve point)**: This is a public key **provably unknown to anyone**,
> deterministically derived from a specific string (e.g., "Lightning Simple Taproot").
> Using it as the internal key effectively "disables" the key path — forcing all spends
> through the script path, ensuring that conditions in the scripts (timelocks, revocation)
> are enforced.

### Revocation Mechanism: How Cheating Is Punished

Lightning channel security relies on the **revocation mechanism**. During each state update:

```
State N → State N+1:
  1. Both parties construct new commitment transactions (state N+1)
  2. Both parties exchange state N's revocation secret (the private key portion of the revocation key)
  3. State N is now "invalidated" — if either party broadcasts it, the other can seize all funds

Cheating punishment flow:
  1. Bob broadcasts the invalidated state N commitment transaction
  2. Alice detects this, uses the revocation secret Bob previously gave her to derive the revocation key
  3. Alice spends the to_local output's revocation path, seizing all of Bob's funds
  4. Punishment complete — Bob loses all channel balance for cheating
```

This is why the to_local output must have a delay —
if Bob honestly broadcasts the latest state, he waits N blocks then reclaims his funds;
if Bob cheats by broadcasting an old state, Alice detects and executes punishment during the delay period.

### Code: Building the to_local Output's Taproot Script Tree

```python
from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, PublicKey
from bitcoinutils.script import Script

setup('testnet')

alice_priv = PrivateKey('cT3tJP7BjwL25nQ9rHQuSCLugr3Vs5XfFKsTs7j5gHDgULyMmm1y')
bob_priv = PrivateKey('cNxX8M7XU8VNa5ofd8yk1eiKxmVUce6qn4d2Priv89dTLEP5GkzJ')
alice_pub = alice_priv.get_public_key()
bob_pub = bob_priv.get_public_key()

# ===== to_local output's Taproot script tree =====

# In production, the internal key should be a NUMS point (unspendable)
# Here we simplify by using Alice's key as the revocation key
# The concept is identical: the revocation key holder can punish cheating
revocation_pub = alice_pub  # Simplified: actually derived from revocation_basepoint

# Leaf 1: Revocation path — Alice can immediately seize funds
# Production: <local_delay_key> OP_DROP <revocation_key> OP_CHECKSIG
# Simplified: <revocation_key> OP_CHECKSIG
revocation_script = Script([
    revocation_pub.to_x_only_hex(),
    'OP_CHECKSIG'
])

# Leaf 2: Delayed path — Bob waits 10 blocks then spends his own funds
delayed_script = Script([
    bob_pub.to_x_only_hex(),
    'OP_CHECKSIGVERIFY',
    'OP_10',                     # 10 block delay
    'OP_CHECKSEQUENCEVERIFY'
])

# ===== Create to_local Taproot address =====
# Production: internal key = NUMS point (forces script path)
# Simplified: internal key = revocation_pub (Alice can punish via key path or script path)
to_local_address = revocation_pub.get_taproot_address([
    [revocation_script, delayed_script]
])

print(f"to_local address: {to_local_address.to_string()}")
print(f"ScriptPubKey: {to_local_address.to_script_pub_key().to_hex()}")

print(f"\nScript tree structure:")
print(f"  Internal Key: revocation_pub (simplified; production uses NUMS point)")
print(f"      ┌────────────┐")
print(f"      │ Merkle Root│")
print(f"      └─────┬──────┘")
print(f"        ┌───┴────┐")
print(f"   revocation  delayed")
print(f"   (Alice      (Bob delayed")
print(f"    punishes)   spending)")
```

## Force Close: Script Path Spending

When Bob unilaterally broadcasts a commitment transaction, the to_local output he holds
requires waiting through the delay period. If Bob is honest (broadcasting the latest state),
he spends via the script path after the waiting period.

```python
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.utils import ControlBlock
from bitcoinutils.constants import TYPE_RELATIVE_TIMELOCK
from bitcoinutils.transactions import Sequence

# ===== Bob spends via the to_local delayed path =====
commitment_txid = "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3"
to_local_amount = 39700
bob_fee = 300

# Set CSV sequence number (must wait 10 blocks)
seq = Sequence(TYPE_RELATIVE_TIMELOCK, 10)

force_tx = Transaction(
    [TxInput(commitment_txid, 0, sequence=seq.for_input_sequence())],
    [TxOutput(to_local_amount - bob_fee, bob_pub.get_taproot_address().to_script_pub_key())],
    has_segwit=True
)

# Script Path signature
bob_sig = bob_priv.sign_taproot_input(
    force_tx, 0,
    [to_local_address.to_script_pub_key()],
    [to_local_amount],
    script_path=True,
    tapleaf_script=delayed_script,
    tweak=False
)

# Build control block
cb = ControlBlock(
    revocation_pub,                     # Internal public key
    [[revocation_script, delayed_script]],  # Script tree structure
    1,                                   # delayed_script's index in tree
    is_odd=to_local_address.is_odd()
)

# Script Path Witness: [signature, script, control_block]
force_tx.witnesses.append(TxWitnessInput([
    bob_sig,
    delayed_script.to_hex(),
    cb.to_hex()
]))

print("=" * 70)
print("Force Close: to_local Delayed Path Spending (Script Path)")
print("=" * 70)
print(f"Witness elements: 3")
print(f"  [0] Bob signature: 64 bytes (Schnorr)")
print(f"  [1] Script:        {len(delayed_script.to_hex())//2} bytes (delayed spending script)")
print(f"  [2] Control block: {len(cb.to_hex())//2} bytes")
print(f"\nOn-chain exposure:")
print(f"  ✓ Delayed spending script (Bob's CSV path)")
print(f"  ✗ Revocation script (Alice's punishment path) → hidden!")
print(f"  ✗ Other HTLC scripts → hidden!")
```

**Key Observation:** Even during a force close, Taproot only exposes the single script leaf that was executed.
In traditional P2WSH, **any spend** exposes the complete script.

## What Bitcoin Sees vs. What Lightning Sees

### Cooperative Close (Most Common Scenario, >90%)

```
[What Bitcoin Sees]                    [What Lightning Sees]

P2WSH Channel:                         P2WSH Channel:
  Funding: P2WSH output                 Channel ID: xxx
  Closing:                              Final state: Alice=60000, Bob=39700
    witness: [empty, sig_a, sig_b,      Close method: Cooperative
              2-of-2 multisig]          Channel lifetime: 30 days
  Observer concludes:                   Transactions: 1,547
    "Lightning channel close"

Taproot Channel:                        Taproot Channel:
  Funding: P2TR output (BIP86)          Channel ID: yyy
  Closing:                              Final state: Alice=60000, Bob=39700
    witness: [schnorr_sig]              Close method: Cooperative
  Observer concludes:                   Channel lifetime: 30 days
    "Ordinary Taproot transfer"         Transactions: 1,547
```

**The same 1,547 off-chain transactions, the same final balance allocation.**
But the Taproot channel leaves no trace on-chain.

### Force Close (Rare Scenario, <10%)

```
P2WSH force close:                     Taproot force close:
  Exposed: Complete 2-of-2 multisig     Exposed: Only one script leaf
  Exposed: Two separate signatures      Exposed: One Schnorr signature
  Exposed: All script conditions        Hidden: All other script leaves
  Conclusion: 100% confirmed            Conclusion: Some kind of conditional
    as Lightning channel                   script, specifics unknown
```

## Three Tiers of Taproot Channels

Placing Lightning Network Taproot channels in the broader context of this book:

### Tier 1: Data Layer (Chapter 9 Ordinals)

```
Taproot witness → Store inscription data → Indexer parses
```

### Tier 2: Commitment Layer (Chapter 10 RGB)

```
Taproot script path → Embed state commitments → Client-side validation
```

### Tier 3: Protocol Layer (This Chapter — Lightning Network)

```
Taproot key path    → MuSig2 cooperative signing → Indistinguishable payments
Taproot script path → Dispute resolution          → Minimal exposure
Taproot BIP86       → Funding output              → Provably no hidden scripts
Taproot NUMS point  → Force script path           → Ensures timelock enforcement
```

| Tier | Chapter | Taproot Capabilities Used | Core Innovation |
|------|---------|--------------------------|-----------------|
| Data layer | Ch 9 (Ordinals) | Witness space, no script size limits | Witness becomes general-purpose data container |
| Commitment layer | Ch 10 (RGB) | Script path commitments (Tapret) | Cryptographic notary for off-chain computation |
| Protocol layer | Ch 11 (Lightning) | Schnorr linearity, key aggregation, BIP86, NUMS point, script trees | Complex protocols indistinguishable from simple payments |

## HTLC → PTLC: The Next Step for Schnorr Signatures

Taproot's improvements to Lightning extend beyond fund locking and channel closes.
It also brings a fundamental privacy upgrade for **cross-channel payments**.

### Current Approach: HTLC (Hash Time-Locked Contract)

Lightning Network's multi-hop payments rely on HTLCs:

```
Alice → Bob → Carol → Dave
Pay 1000 sats

Steps:
1. Dave generates random number R, computes H = SHA256(R)
2. Dave sends H to Alice (via invoice)
3. Alice to Bob: "If you present SHA256 preimage R, I'll give you 1003 sats"
4. Bob to Carol: "If you present SHA256 preimage R, I'll give you 1001 sats"
5. Carol to Dave: "If you present SHA256 preimage R, I'll give you 1000 sats"
6. Dave reveals R → Carol → Bob → Alice, payment complete
```

**HTLC's Privacy Problem:**

```
Alice → Bob: HTLC(H=0xabcd...)
Bob → Carol:  HTLC(H=0xabcd...)  ← Same hash!
Carol → Dave: HTLC(H=0xabcd...)  ← Same hash!
```

Every hop uses **the same hash value H**. If Bob and Dave collude (or are the same entity),
they can match hash values to discover: these three HTLCs belong to the same payment.

### Future Approach: PTLC (Point Time-Locked Contract)

Taproot's Schnorr signatures make PTLCs possible. PTLCs use **elliptic curve points** instead of hash values,
and **adaptor signatures** instead of hash preimage reveals:

```
Alice → Bob:  PTLC(Point_1)
Bob → Carol:  PTLC(Point_2)  ← Different point!
Carol → Dave: PTLC(Point_3)  ← Different point!
```

**Every hop's "lock" is different** — even if Bob and Dave collude,
they cannot tell these PTLCs belong to the same payment by comparison.

### Why Schnorr/Taproot Is Required

PTLCs rely on the mathematical properties of Schnorr signatures — **adaptor signatures**:

```
Adaptor Signature core idea:
  
  Alice gives Bob an "incomplete signature" s'
  s' alone cannot pass verification
  But: s' + t = s (valid signature)
  where t is a secret value
  
  When Bob sees the complete signature s appear on-chain, he can compute t = s - s'
  → t is the "lock's" key, passed along the payment path
```

| Property | HTLC | PTLC |
|----------|------|------|
| Locking mechanism | Hash preimage (SHA256) | Elliptic curve point (adaptor signature) |
| Cross-hop correlation | High (same hash value) | None (different point per hop) |
| Signature scheme dependency | ECDSA or Schnorr | Schnorr only |
| On-chain footprint | Exposes hash and preimage | Only signatures (indistinguishable) |
| Requires Taproot | No | Yes (requires Schnorr) |

> **Engineering Status Note:** As of late 2025, PTLCs in Lightning Network are still in the
> specification discussion and early implementation stage. Current Simple Taproot Channels
> still use HTLCs, which allows Taproot channel nodes to interoperate with traditional channel nodes.
> Full PTLC deployment requires all nodes in a payment path to support Taproot channels.

## Industry Progress: Taproot Channels Are Already Running

Taproot Lightning channels are not theoretical constructs — they are running on mainnet,
though still maturing.

### LND (Lightning Network Daemon)

LND has supported experimental Simple Taproot Channels since v0.17.0-beta (October 2023):

```bash
# Enable Taproot channels
lnd --protocol.simple-taproot-chans
```

As of mid-2025, LND has iterated to v0.19.0-beta. Key status of Taproot channels:
- **MuSig2 funding output** implemented — funding output uses aggregate key + BIP86
- **Cooperative close** via key path spending (single Schnorr signature)
- **Private/unannounced channels only** — announced channels require Gossip 1.75 protocol completion
- **Still using HTLCs** — PTLCs not yet implemented
- **RBF cooperative close** incompatible with Taproot channels (requires additional nonce logic)

### Eclair

Eclair (ACINQ's Lightning implementation) added Simple Taproot Channels support
in August 2025 via PR #3103, marking progress toward multi-implementation interoperability.

### ZEUS Wallet

ZEUS v0.8.0 became the **first mobile wallet to support Taproot channels**.
Users can open Taproot channels directly through ZEUS's built-in LND node.
ZEUS documentation notes that Taproot channels offer comprehensive advantages
in privacy and fees over traditional channels, with the only concern being
the relative newness of this feature in LND.

### Current Limitations and Roadmap

| Status | Description |
|--------|-------------|
| ✅ Implemented | MuSig2 funding output, key-path cooperative close |
| ✅ Implemented | Private/unannounced Taproot channels |
| ⏳ In progress | Gossip 1.75 (required for announced Taproot channels) |
| ⏳ In progress | RBF cooperative close + Taproot channel compatibility |
| 🔮 Future | PTLC replacing HTLC |
| 🔮 Future | Full cross-implementation interoperability |

> **Specification Reference**: Simple Taproot Channels' BOLT specification is defined in
> [lightning/bolts PR #995](https://github.com/lightning/bolts/pull/995),
> as an "extension BOLT" (features 80/81), combining
> BIP 340 (Schnorr), BIP 341 (Taproot), and BIP 327 (MuSig2).
> Elle Mouton's blog post [Taproot Channel Transactions](https://ellemouton.com/posts/taproot-chan-txs/)
> provides very detailed diagrams of the complete commitment transaction structure.

## Exercises

### Exercise 1: Build and Compare Two Funding Addresses

1. Use this chapter's code to create both P2WSH and Taproot (BIP86) funding addresses
2. Compare their ScriptPubKeys
3. Answer: How much information can an external observer extract from the ScriptPubKey?
4. Think: Why does the Taproot funding output use BIP86 instead of including a script tree?

### Exercise 2: Find Real Channel Transactions on mempool.space

1. On [mempool.space](https://mempool.space), search for a real **P2WSH channel cooperative close transaction**
   - Hint: Look for P2WSH spends with a 2-of-2 multisig script in the witness
   - Observe the witness structure: empty element + two signatures + complete script

2. Search for a real **Taproot channel cooperative close transaction**
   - Hint: This is harder — because it looks identical to an ordinary Taproot payment!
   - Think: How could you confirm a transaction is a channel close rather than an ordinary payment?

3. Compare the witness sizes and structures of both

### Exercise 3: Decode a Real Force Close Transaction

1. On mempool.space, find a Taproot channel **force close transaction**
   - Hint: Look for Taproot script path spends with script + control block in the witness
2. Identify the internal public key in the control block
3. Think: How much information can an observer derive from this transaction?

### Exercise 4: Simulate a to_local Force Close

1. Using this chapter's code, actually build a spend via the to_local delayed path on testnet
2. Set the CSV timelock to 2 blocks
3. Verify: Is spending rejected during the delay period? Does it succeed after?
4. Observe what the witness exposes versus what it hides

### Exercise 5: Experience Real Taproot Channels (Optional)

Use [Polar](https://lightningpolar.com/) to simulate a Lightning Network environment locally:

1. Create a network with two LND nodes
2. Enable `--protocol.simple-taproot-chans` in the LND configuration
3. Open a Taproot channel
4. Inspect the funding transaction in Polar's block explorer
5. Close the channel and compare the funding and closing transaction witnesses

> **Alternative**: If you prefer not to use Polar, install ZEUS v0.8.0+
> connected to a testnet node to experience Taproot channel operations on mobile.

## Engineering Summary: Taproot as a Privacy Protocol Layer

### Architectural Innovation

**Traditional Lightning Channels (P2WSH):**
```
Funding:          P2WSH 2-of-2 → identifiable as multisig
Cooperative close: Exposes complete script + two signatures → confirmed as channel
Force close:       Exposes complete script + timelock logic → fully transparent
Commitment tx:     P2WSH outputs, scripts fully exposed
```

**Taproot Lightning Channels (P2TR):**
```
Funding:          P2TR BIP86 → indistinguishable from ordinary payment
Cooperative close: Single Schnorr signature (key path) → indistinguishable from ordinary payment
Force close:       Exposes one script leaf (script path) → minimal information exposure
Commitment tx:     P2TR outputs, NUMS point + script trees, only executed path exposed
```

### Four Uses of Taproot in Lightning Channels

| Usage | Applied To | Effect |
|-------|-----------|--------|
| BIP86 (key-only) | Funding output | Provably no hidden scripts, pure key path |
| MuSig2 key aggregation | Funding output key path | 2-of-2 compressed into single signature |
| NUMS point | to_local, to_remote internal keys | Forces script path, ensures timelock enforcement |
| Script trees | All commitment tx outputs | Revocation/delay/HTLC, only executed path exposed |

### Complete Book Taproot Application Overview

```
Taproot capability dimensions:

1. Witness space ─────────→ Ch 9 Ordinals: Data storage
                            No script size limits, witness becomes data container

2. Script path commitment ─→ Ch 10 RGB: Cryptographic anchoring
                             Tapret commits off-chain state, client-side validation

3. Schnorr linearity ──────→ Ch 11 Lightning: Privacy protocol
   + Key aggregation          MuSig2 cooperative signing, indistinguishable payments
   + BIP86                    Fund locking, provably no hidden scripts
   + NUMS point               Forces script path, ensures dispute logic
   + Script trees             Commitment transactions, minimal exposure
   + Adaptor signatures       PTLCs eliminate payment correlation (future)
```

## Conclusion

Lightning Network Taproot channels demonstrate Taproot's third capability dimension — the **privacy protocol layer**.

1. **Funding Output (BIP86)**: Fund locking evolves from identifiable P2WSH 2-of-2 to a pure key-path Taproot output, indistinguishable on-chain
2. **Cooperative Close (Key Path)**: MuSig2 aggregate signature, from ~249 bytes down to 64 bytes, identical to ordinary payments
3. **Commitment Transaction (Script Tree)**: to_local uses NUMS + revocation/delay scripts, HTLCs use revocation key + preimage/timeout scripts
4. **Force Close (Script Path)**: Only the executed script leaf is exposed, all other paths remain hidden forever
5. **PTLC Prospects**: Adaptor signatures will eliminate multi-hop payment on-chain correlation

If Ordinals proved that Taproot can make witness do **unexpected things**,
and RGB proved that Taproot can provide **cryptographic notarization** for off-chain computation,
then Lightning Network channels prove that Taproot can make the most complex multi-party protocols
leave **absolutely no trace** on-chain.

Recalling the opening of Chapter 5:

> *Taproot's fundamental breakthrough is **payment uniformity**.*

Lightning Network Taproot channels are the most direct and important realization of that vision.

**Complex contracts should leave no more on-chain trace than simple payments.**
