# Chapter 10: RGB - Client-Side Validation & Taproot Commitments

## Why This Chapter Matters

RGB represents the most rigorous engineering application of Taproot's commitment capabilities. While Chapter 9 showed how Taproot's witness can store data (Ordinals/BRC-20), RGB demonstrates how Taproot's script-path commitments can anchor **off-chain contract state** with cryptographic guarantees.

From an engineering perspective, this chapter addresses:

- Why Bitcoin cannot execute smart contracts (by design)
- How Taproot commitments enable cryptographic anchoring without on-chain execution
- How single-use seals (UTXOs) become state carriers
- Why client-side validation is more powerful than indexer-based protocols
- The complete RGB workflow: Invoice → Transfer → Consignment → PSBT → Broadcast

RGB showcases Taproot's second capability tier: not just storing data, but serving as a **cryptographic notary for off-chain computation**.

## The Problem: Why Bitcoin Cannot Execute Smart Contracts

Bitcoin's architecture intentionally avoids on-chain contract execution. Understanding why is crucial to appreciating RGB's design.

### What Bitcoin Nodes Cannot Do

Bitcoin nodes cannot:
- Store arbitrary state
- Execute arbitrary logic
- Maintain global contract storage
- Run Turing-complete programs
- Support contract-level fees

This is **by design**, not a limitation. Bitcoin's consensus layer must remain:
- **Minimal**: Every node must verify every transaction
- **Bounded**: Verification costs must be predictable
- **Scalable**: The system must handle global transaction volume

### RGB's Paradigm Reversal

RGB solves this by reversing the paradigm:

**Nothing is executed on-chain.**

**Everything is verified off-chain.**

**Bitcoin only stores commitments.**

This architectural choice enables:
- Unlimited contract complexity (off-chain)
- Predictable on-chain costs (commitment storage only)
- Scalability (state grows off-chain, not on-chain)
- Privacy (contract logic never revealed on-chain)

## The Two Tiers of Taproot Applications

Before diving into RGB's mechanics, let's establish a conceptual framework for understanding how protocols use Taproot differently.

### Tier 1: Data Storage (Ordinals/BRC-20)

Chapter 9 covered this tier:
- Witness stores arbitrary data (images, JSON, etc.)
- Data is **revealed** when spent
- Indexers parse and maintain state
- Simple, but requires trust in indexers
- Use case: Data storage, simple tokens

### Tier 2: Cryptographic Commitments (RGB)

This chapter covers the second tier:
- Script-path **commits** to state (not stores it)
- State is never revealed on-chain
- Clients verify cryptographically
- Complex, but trustless
- Use case: Smart contracts, complex assets

The key distinction: Ordinals stores data **in** the witness; RGB stores a **commitment to** data in the script-path. The actual data lives off-chain and is transmitted via **consignments**.

## Core RGB Concepts

Before examining the workflow, we must understand RGB's foundational concepts.

### Single-Use Seals: UTXOs as State Carriers

This is RGB's key insight:

> **Every RGB contract state is bound to a specific UTXO.**
>
> **Spending the UTXO = updating the contract state.**

This fits Bitcoin perfectly:
- Each state transition uses a new UTXO
- Bitcoin ensures the UTXO cannot be reused (double-spend prevention)
- The commitment enforces valid transitions (cryptographic proof required)

**State Binding:**
```
UTXO A → State S1 (committed via Tapret)
```

**State Transition:**
```
Spend UTXO A → Create UTXO B → State S2 (committed via Tapret)
```

Bitcoin's role:
- Ensures UTXO A cannot be spent twice
- Stores the commitment hash
- Provides ordering and timestamping

RGB's role:
- Validates state transition cryptographically
- Ensures S1 → S2 is valid according to contract rules
- Maintains state history off-chain

### Consignment: The Proof Bundle

A **consignment** is the off-chain proof bundle that contains:
- Complete state transition history
- Cryptographic proofs of validity
- Anchor transaction references
- Contract schema and metadata

When Alice transfers tokens to Bob, she doesn't just send a transaction—she sends a **consignment file** that Bob must validate before accepting. This is the essence of client-side validation: the receiver verifies everything cryptographically, trusting no one.

> **Note on History Growth**: Consignments accumulate the full state transition history back to genesis. In multi-hop transfers, each consignment grows as it includes all previous transitions. This is a trade-off: complete verifiability at the cost of increasing consignment size. For high-frequency transfers, techniques like state pruning and checkpointing are being developed.

### Invoice: The Payment Request

An **invoice** is how the receiver requests a specific amount of assets to a specific UTXO. It contains:
- Contract ID
- Interface type (e.g., RGB20Fixed)
- Amount requested
- Destination UTXO (blinded or explicit)

The sender uses this invoice to construct the transfer.

### Tapret and Opret Commitments

RGB supports two commitment schemes for anchoring state transitions:

**Tapret (Taproot-based)**: Embeds a 64-byte commitment as an unspendable script leaf in the Taproot script tree. The commitment is placed at the first level of the script tree, invisible until the UTXO is spent via script-path.

```
Taproot Output
├── Key Path: Normal spending
└── Script Path (Level 1):
    ├── Tapret Commitment (64 bytes, unspendable)
    └── Other scripts (shifted to Level 2+)
```

**Opret (OP_RETURN-based)**: Places a 34-byte commitment in the first OP_RETURN output. Useful for older hardware that doesn't support Taproot.

Most modern RGB implementations use Tapret because:
- Better privacy (commitment hidden in script tree)
- Smaller on-chain footprint when not revealed
- Compatible with existing Taproot scripts

Bitcoin sees only a normal Taproot address. The RGB commitment is invisible until the UTXO is spent, and even then, only the commitment hash is revealed—not the actual state data.

## RGB Workflow: From Invoice to Confirmation

Let's trace through a complete RGB20 token transfer using actual CLI commands.

### Environment Setup

This workflow uses the bitlight-local-env development environment with RGB CLI v0.11.x. CLI syntax may vary between versions—always check the [RGB GitHub](https://github.com/RGB-Tools) for the latest documentation.

```bash
# Clone and start the environment
git clone https://github.com/bitlightlabs/bitlight-local-env-public
cd bitlight-local-env-public
docker-compose up -d

# Verify services
curl http://localhost:3002/blocks/tip/height  # Esplora API
```

The environment provides:
- Bitcoin Core (regtest mode)
- Electrs/Esplora indexer (port 3002)
- Pre-configured wallets (Alice, Bob)

### Step 1: Contract Deployment (One-Time Setup)

Before any transfers, someone must deploy the RGB20 contract:

```bash
# Alice deploys the contract
rgb -d .alice -n regtest import ./contracts/rgb20-simplest.rgb \
    --esplora="http://localhost:3002"

# Verify contract import
rgb -d .alice -n regtest state <CONTRACT_ID> RGB20Fixed \
    --esplora="http://localhost:3002"
```

The contract specifies:
- Token name and ticker
- Total supply (fixed for RGB20Fixed)
- Initial owner (Alice's UTXO)

### Step 2: Bob Generates Invoice

Bob wants to receive 500 tokens. He generates an invoice specifying:
- The contract he wants tokens from
- The interface type (RGB20Fixed)
- The amount (500)
- His receiving UTXO

```bash
# Bob generates invoice for 500 tokens
rgb -d .bob -n regtest invoice \
    <CONTRACT_ID> \
    RGB20Fixed \
    500 \
    --esplora="http://localhost:3002"
```

Output:
```
rgb:BppYGUUL-Qboz3UD-czwAaVV-!!Jkr1a-SE1!m1f-Cz$b0xs/RGB20Fixed/500+utxob:
egXsFnw-E1z4Cng-NKV3r1J-BH42m7P-CpLTXYa-LQFVM5Y
```

This invoice is sent to Alice off-chain (via any channel: email, messaging, Lightning, etc.).

### Step 3: Alice Creates Transfer

Alice uses Bob's invoice to create the transfer. This generates two outputs:
- A **consignment file** (proof bundle for Bob)
- A **PSBT** (Partially Signed Bitcoin Transaction)

```bash
# Alice creates transfer based on Bob's invoice
rgb -d .alice -n regtest transfer \
    "<BOB_INVOICE>" \
    transfer_to_bob.consignment \
    --esplora="http://localhost:3002"
```

Output:
```
Transfer created successfully.
Consignment: transfer_to_bob.consignment
PSBT: transfer_to_bob.psbt
```

At this point:
- The consignment contains the complete proof of Alice's ownership and the state transition
- The PSBT contains the Bitcoin transaction that will anchor the new state
- Neither has been broadcast yet

### Step 4: Bob Validates and Accepts Consignment

Bob receives the consignment file and must validate it before accepting:

```bash
# Bob validates the consignment
rgb -d .bob -n regtest validate \
    transfer_to_bob.consignment \
    --esplora="http://localhost:3002"
```

Output:
```
Consignment is valid.
```

If valid, Bob accepts:

```bash
# Bob accepts the consignment
rgb -d .bob -n regtest accept \
    transfer_to_bob.consignment \
    --esplora="http://localhost:3002"
```

**What Bob's client validates:**
- Alice's UTXO exists and commits to the claimed state
- The state transition follows RGB20Fixed rules
- Token amounts are conserved
- All cryptographic signatures are valid
- No double-spend (the UTXO hasn't been spent elsewhere)

This is **client-side validation**: Bob verifies everything himself, trusting no indexer or third party.

### Step 5: Alice Signs and Broadcasts PSBT

After Bob accepts, Alice signs the Bitcoin transaction:

```bash
# Sign the PSBT (using bitcoin-cli or Sparrow)
bitcoin-cli -rpcwallet=alice signrawtransactionwithwallet \
    $(cat transfer_to_bob.psbt | base64 -d | xxd -p | tr -d '\n')

# Or using Sparrow Wallet for hardware wallet signing
# File → Open Transaction → Select PSBT → Sign → Broadcast
```

Then broadcast:

```bash
# Broadcast the signed transaction
bitcoin-cli sendrawtransaction <signed_tx_hex>

# Mine a block (regtest only)
bitcoin-cli generatetoaddress 1 <mining_address>
```

### Step 6: Verify Final State

Both parties verify the transfer completed:

```bash
# Alice checks her balance
rgb -d .alice -n regtest state <CONTRACT_ID> RGB20Fixed \
    --esplora="http://localhost:3002"

# Bob checks his balance  
rgb -d .bob -n regtest state <CONTRACT_ID> RGB20Fixed \
    --esplora="http://localhost:3002"
```

**Result:**
- Alice: Previous balance minus 500
- Bob: Previous balance plus 500 (bound to new UTXO)

## What Bitcoin Sees vs. What RGB Sees

This distinction is crucial for understanding RGB's architecture.

### Bitcoin's View

Bitcoin only sees:
```
Transaction:
  Input: Alice's UTXO (spent)
  Output 0: Bob's new UTXO (Taproot address)
  Output 1: Alice's change UTXO (Taproot address)
```

The transaction looks like any normal Taproot payment. There is:
- No token data visible
- No contract logic visible
- No indication this is an RGB transaction
- Just a standard Bitcoin transaction with Taproot outputs

### RGB's View

RGB sees (via consignment):
```
State Transition:
  Input State: Alice owns 10000 tokens (bound to her old UTXO)
  Output State 0: Bob owns 500 tokens (bound to his new UTXO)
  Output State 1: Alice owns 9500 tokens (bound to her change UTXO)
  Proof: Cryptographic proof of valid transition
  Anchor: Bitcoin transaction ID
```

The entire token logic exists off-chain, with Bitcoin providing only the anchor.

## RGB vs. Ordinals/BRC-20: Architectural Comparison

| Feature | Ordinals/BRC-20 | RGB |
|---------|-----------------|-----|
| **Data Location** | Witness (on-chain, revealed) | Off-chain (consignment files) |
| **On-Chain Footprint** | Full data stored | Only commitment hash |
| **Verification** | Indexer (trusted) | Client-side (cryptographic) |
| **State Model** | Satoshi-based | UTXO-based contract state |
| **Trust Model** | Trust indexer consensus | Verify cryptographically |
| **Privacy** | Data revealed on spend | Data never on-chain |
| **Scalability** | Limited by block space | Unlimited (off-chain state) |
| **Recovery** | Depends on indexer | Consignment history |
| **Transmission** | On-chain (block space) | Off-chain (requires secure channel) |

### The Trade-offs

**Ordinals/BRC-20**: Simpler architecture, but limited by block space and indexer trust.

**RGB**: Superior scalability and privacy, but requires:
- Secure off-chain channels for consignment transmission
- Users to manage consignment files (backup, storage)
- Ecosystem tooling for wallet and application support

### The Indexer Trust Problem

BRC-20's correctness depends on which indexer you trust:
- Different indexers may disagree on balances
- Cursed inscriptions caused indexer divergence
- No on-chain arbitration mechanism

RGB eliminates this entirely:
- Every client validates independently
- State transitions are cryptographically provable
- No indexer consensus required

## Asset Recovery: Consignment as State History

One of RGB's most powerful features is **state recovery via consignments**.

### The Recovery Principle

Since all state transitions are recorded in consignments:
- If you have the consignment history, you can reconstruct your state
- No need to trust any indexer or third party
- State is recoverable even if your local database is corrupted

### Recovery Workflow

> **Important**: Consignments must be re-accepted in **chronological order** (oldest first) to correctly rebuild the state history. Out-of-order acceptance will fail validation.

```bash
# Alice loses her local RGB state but has consignment backups

# Re-import the contract
rgb -d .alice_recovered -n regtest import ./contracts/rgb20-simplest.rgb \
    --esplora="http://localhost:3002"

# Re-accept historical consignments IN CHRONOLOGICAL ORDER
rgb -d .alice_recovered -n regtest accept alice_issuance.consignment \
    --esplora="http://localhost:3002"

rgb -d .alice_recovered -n regtest accept bob_to_alice_refund.consignment \
    --esplora="http://localhost:3002"

# State is now reconstructed
rgb -d .alice_recovered -n regtest state <CONTRACT_ID> RGB20Fixed \
    --esplora="http://localhost:3002"
```

This is fundamentally different from BRC-20:
- BRC-20: If indexers disagree, there's no authoritative source
- RGB: Consignment history is the authoritative source, verifiable by anyone

## Exercise: Multi-Hop Transfer (Alice → Bob → Dave)

To solidify your understanding, complete this exercise that extends the basic transfer to a three-party scenario.

### Setup

1. Create Dave's wallet:
```bash
# In bitlight-local-env
make dave-cli

# Create RGB wallet for Dave
rgb -d .dave -n regtest create default --tapret-key-only \
    "<DAVE_XPUB>" \
    --esplora="http://localhost:3002"

# Import the contract
rgb -d .dave -n regtest import ./contracts/rgb20-simplest.rgb \
    --esplora="http://localhost:3002"
```

2. Fund Dave with Bitcoin (for UTXO):
```bash
# Send 1 BTC to Dave's address
bitcoin-cli -rpcwallet=core sendtoaddress <dave_address> 1
bitcoin-cli generatetoaddress 1 <mining_address>
```

### Transfer: Bob → Dave

3. Dave generates invoice:
```bash
rgb -d .dave -n regtest invoice <CONTRACT_ID> RGB20Fixed 200 \
    --esplora="http://localhost:3002"
```

4. Bob creates transfer:
```bash
rgb -d .bob -n regtest transfer "<DAVE_INVOICE>" \
    bob_to_dave.consignment \
    --esplora="http://localhost:3002"
```

5. Dave validates and accepts:
```bash
rgb -d .dave -n regtest validate bob_to_dave.consignment \
    --esplora="http://localhost:3002"

rgb -d .dave -n regtest accept bob_to_dave.consignment \
    --esplora="http://localhost:3002"
```

6. Bob signs and broadcasts PSBT, then verify:
```bash
# Sign, broadcast, mine block

# Verify all balances
rgb -d .alice -n regtest state <CONTRACT_ID> RGB20Fixed --esplora="http://localhost:3002"
rgb -d .bob -n regtest state <CONTRACT_ID> RGB20Fixed --esplora="http://localhost:3002"
rgb -d .dave -n regtest state <CONTRACT_ID> RGB20Fixed --esplora="http://localhost:3002"
```

### What This Exercise Demonstrates

- **Multi-hop capability**: Tokens can flow through arbitrary transfer paths
- **Client-side validation scales**: Each party validates only what they receive
- **UTXO consolidation**: RGB can merge multiple UTXOs during transfer
- **Complete audit trail**: Dave's consignment contains the full history back to issuance
- **Consignment growth**: Notice that Dave's consignment is larger than Bob's, as it includes both Alice→Bob and Bob→Dave transitions

> **Production Note**: For mainnet or testnet with real value, use hardware wallets (e.g., Sparrow Wallet with Ledger/Trezor) for PSBT signing. Never expose private keys in CLI for production assets.

## Advanced: RGB v0.12 with Testnet

For production-like testing, RGB v0.12 supports Bitcoin testnet with Sparrow Wallet integration.

### Environment

```bash
# Bitcoin Core testnet (lightmode for faster sync)
bitcoind -testnet -lightmode

# Electrs indexer
electrs --network testnet --electrum-rpc-addr 127.0.0.1:60001

# RGB CLI v0.12
rgb --version  # Should show v0.12.x
```

### Contract Issuance (v0.12 YAML Format)

RGB v0.12 uses YAML configuration for contract issuance:

```yaml
# aarontest_issue.yaml
consensus: bitcoin
testnet: true
issuer:
  codexId: 7C15w3W1-L0T~zXw-Aeh5~kV-Zquz729-HXQFKQW-_5lX9O8
  version: 0
  checksum: AYkSrg
name: AARONTEST
method: issue
timestamp: "2025-09-01T19:30:00+00:00"
global:
  - name: ticker
    verified: ATEST
  - name: name
    verified: AARON Test Token
  - name: precision
    verified: centiMilli
  - name: issued
    verified: 10000
owned:
  - name: balance
    seal: <YOUR_UTXO_TXID>:<VOUT>
    data: 10000
```

Key findings from v0.12 experimentation:
- Avoid special characters (hyphens, underscores) in contract names to prevent parsing issues
- `seal` must reference a UTXO you control
- Issuance is purely off-chain, bound to existing UTXO
- Sparrow Wallet works well for PSBT signing

## Engineering Summary: Taproot as Cryptographic Notary

RGB demonstrates Taproot's highest capability tier.

### The Architectural Innovation

**Traditional Smart Contracts (Ethereum):**
```
On-chain execution → Global state → High costs → Limited scalability
```

**RGB (Bitcoin + Taproot):**
```
Off-chain execution → Cryptographic commitments → Low costs → Unlimited scalability
```

### What Taproot Provides to RGB

1. **Tapret Commitments**: Embed state commitments in script-path without revealing data
2. **Address Uniformity**: RGB transactions look identical to normal Taproot payments
3. **Single-Use Seals**: UTXOs become cryptographically-bound state carriers
4. **Privacy Preservation**: Contract logic never appears on-chain

### Why This Matters

RGB proves that Bitcoin + Taproot can support:
- Complex smart contracts (off-chain logic, on-chain anchoring)
- Trustless verification (client-side validation, no indexers)
- Unlimited scalability (state grows off-chain)
- Strong privacy (only commitments on-chain)
- Recoverable state (consignment history)

## Conclusion

RGB represents the most rigorous engineering application of Taproot's commitment capabilities. It demonstrates:

1. **Client-Side Validation**: All contract logic verified off-chain, cryptographically
2. **Single-Use Seals**: UTXOs become state carriers, perfectly aligned with Bitcoin's model
3. **Consignment-Based Transfer**: Proof bundles transmitted off-chain, anchored on-chain
4. **Trustless Architecture**: No indexers, no third parties, verify everything yourself
5. **Recoverable State**: Consignment history enables state reconstruction

While Ordinals/BRC-20 showed how Taproot's witness can store data (Tier 1), RGB shows how Taproot's script-path commitments can anchor complex off-chain computation with cryptographic guarantees (Tier 2).

The engineering reality: Taproot didn't make Bitcoin "do smart contracts" on-chain. Taproot provided cryptographic commitment capabilities, and RGB discovered how to use these capabilities to build a trustless, scalable, privacy-preserving smart contract system that perfectly aligns with Bitcoin's architecture.

> **Ecosystem Note**: While RGB offers superior scalability and privacy compared to indexer-based protocols, its adoption depends on ecosystem tooling—wallets that support consignment handling, secure transmission channels, and user-friendly interfaces for state management. As of 2025, this ecosystem is maturing rapidly with tools like Bitlight, MyCitadel, and integration with Lightning Network via Bifrost.

**Taproot = Bitcoin's cryptographic notary for off-chain computation.**

RGB is the most rigorous implementation of this paradigm.