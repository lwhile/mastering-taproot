# Chapter 8: Four-Leaf Taproot Script Tree

This directory contains code examples for Chapter 8, demonstrating the complete implementation of four-leaf Taproot script trees with enterprise-grade multi-path spending.

## Overview

This chapter demonstrates how to build and spend from a four-leaf Taproot script tree, which contains:
- **Script Path 0**: SHA256 Hash Lock (anyone with preimage "helloworld" can spend)
- **Script Path 1**: 2-of-2 Multisig (requires both Alice and Bob signatures)
- **Script Path 2**: CSV Timelock (Bob can spend after 2 blocks)
- **Script Path 3**: Simple Signature (Bob can spend immediately)
- **Key Path**: Alice can spend directly (maximum privacy)

## Setup

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Files

### `01_create_four_leaf_taproot.py`
Creates a four-leaf Taproot address containing all four scripts.

**Expected Output:**
- Taproot Address: `tb1pjfdm902y2adr08qnn4tahxjvp6x5selgmvzx63yfqk2hdey02yvqjcr29q`

**Script Tree Structure:**
```
        Merkle Root
       /            \
  Branch0        Branch1
  /      \       /      \
Script0 Script1 Script2 Script3
(Hash)  (Multi)  (CSV)   (Sig)
```

**Run:**
```bash
python3 01_create_four_leaf_taproot.py
```

### `02_hashlock_path_spending.py`
Implements Hash Lock Script Path spending using the preimage "helloworld".

**Based on Transaction:**
- TXID: `1ba4835fca1c94e7eb0016ce37c6de2545d07d84a97436f8db999f33a6fd6845`
- Input TXID: `245563c5aa4c6d32fc34eed2f182b5ed76892d13370f067dc56f34616b66c468`

**Witness Structure:**
- `[0]`: Preimage hex (`68656c6c6f776f726c64`)
- `[1]`: Hash Script hex
- `[2]`: Control Block (97 bytes)

**Run:**
```bash
python3 02_hashlock_path_spending.py
```

### `03_multisig_path_spending.py`
Implements 2-of-2 Multisig Script Path spending using OP_CHECKSIGADD.

**Based on Transaction:**
- TXID: `1951a3be0f05df377b1789223f6da66ed39c781aaf39ace0bf98c3beb7e604a1`
- Input TXID: `1ed5a3e97a6d3bc0493acc2aac15011cd99000b52e932724766c3d277d76daac`

**Witness Structure:**
- `[0]`: Bob's signature (consumed second)
- `[1]`: Alice's signature (consumed first)
- `[2]`: Multisig Script hex
- `[3]`: Control Block (97 bytes)

**Key Concepts:**
- Uses OP_CHECKSIGADD (Tapscript style, more efficient than OP_CHECKMULTISIG)
- Signature order: Bob first, Alice second (but consumed in reverse order)
- Script execution: OP_0 → verify Alice → verify Bob → OP_2 → OP_EQUAL

**Run:**
```bash
python3 03_multisig_path_spending.py
```

### `04_csv_timelock_path_spending.py`
Implements CSV Timelock Script Path spending.

**Based on Transaction:**
- TXID: `98361ab2c19aa0063f7572cfd0f66cb890b403d2dd12029426613b40d17f41ee`
- Input TXID: `9a2bff4161411f25675c730777c7b4f5b2837e19898500628f2010c1610ac345`

**Witness Structure:**
- `[0]`: Bob's signature
- `[1]`: CSV Script hex
- `[2]`: Control Block (97 bytes)

**Key Concepts:**
- Requires special sequence value in transaction input
- Relative timelock: 2 blocks
- Bob can spend after waiting 2 blocks

**Run:**
```bash
python3 04_csv_timelock_path_spending.py
```

### `05_simple_sig_path_spending.py`
Implements Simple Signature Script Path spending.

**Based on Transaction:**
- TXID: `1af46d4c71e121783c3c7195f4b45025a1f38b73fc8898d2546fc33b4c6c71b9`
- Input TXID: `632743eb43aa68fb1c486bff48e8b27c436ac1f0d674265431ba8c1598e2aeea`

**Witness Structure:**
- `[0]`: Bob's signature
- `[1]`: Simple Signature Script hex
- `[2]`: Control Block (97 bytes)

**Key Concepts:**
- Simplest script path
- Bob can spend immediately using signature

**Run:**
```bash
python3 05_simple_sig_path_spending.py
```

### `06_key_path_spending.py`
Implements Key Path spending (maximum privacy).

**Based on Transaction:**
- TXID: `1e518aa540bc770df549ec9836d89783ca19fc79b84e7407a882cbe9e95600da`
- Input TXID: `42a9796a91cf971093b35685db9cb1a164fb5402aa7e2541ea7693acc1923059`

**Witness Structure:**
- `[0]`: Alice's signature (64 bytes only!)

**Key Concepts:**
- Maximum privacy: No script information revealed
- Most efficient: Only 64-byte signature
- Indistinguishable from simple Taproot payment
- Uses Alice's tweaked private key

**Run:**
```bash
python3 06_key_path_spending.py
```

### `07_verify_control_blocks.py`
Verifies Control Blocks and all transaction TXIDs by actually running all spending scripts.

**Key Features:**
- **Actual Verification**: Runs all five spending scripts and compares generated TXIDs with on-chain transactions
- Control Block structure: 97 bytes for four-leaf (vs 33 for single, 65 for dual)
- Two-level Merkle proofs: sibling + parent sibling
- All scripts share the same internal public key
- All five spending paths use the same Taproot address

**Verification Results:**
- Script Path 0 (Hash Lock): ✅ MATCH
- Script Path 1 (Multisig): ✅ MATCH
- Script Path 2 (CSV Timelock): ✅ MATCH
- Script Path 3 (Simple Signature): ✅ MATCH
- Key Path: ✅ MATCH

**Run:**
```bash
python3 07_verify_control_blocks.py
```

## Key Technical Points

### Control Block Size Comparison

| Script Tree Type | Control Block Size | Structure |
|------------------|-------------------|-----------|
| Single-leaf | 33 bytes | [version+parity] + [internal_pubkey] |
| Dual-leaf | 65 bytes | [version+parity] + [internal_pubkey] + [sibling_hash] |
| Four-leaf | 97 bytes | [version+parity] + [internal_pubkey] + [sibling1] + [sibling2] |

### Merkle Tree Structure for Four-Leaf

```
Level 0: Script0, Script1, Script2, Script3 (TapLeaf hashes)
Level 1: Branch0 = TapBranch(Script0, Script1)
         Branch1 = TapBranch(Script2, Script3)
Level 2: Merkle Root = TapBranch(Branch0, Branch1)
```

### OP_CHECKSIGADD vs OP_CHECKMULTISIG

**OP_CHECKSIGADD Advantages:**
- More efficient: verifies one by one, stops on failure
- Simpler stack operations: clear counter mechanism
- Native x-only public key support (32 bytes)
- No off-by-one issues

**OP_CHECKMULTISIG Disadvantages:**
- Must check all possible signature combinations
- Complex stack operations
- Requires 33-byte compressed public keys
- Off-by-one bug in legacy Bitcoin Script

### CSV Timelock Implementation

1. Create Sequence object: `Sequence(TYPE_RELATIVE_TIMELOCK, relative_blocks)`
2. Use in script: `seq.for_script()` pushes sequence value
3. Use in input: `seq.for_input_sequence()` sets nSequence
4. Script verifies: `OP_CHECKSEQUENCEVERIFY` checks relative timelock

## Transaction Verification

All five spending paths use the **same Taproot address**, proving they originate from the same four-leaf script tree:

- **Taproot Address (Input)**: `tb1pjfdm902y2adr08qnn4tahxjvp6x5selgmvzx63yfqk2hdey02yvqjcr29q`
- **Output Address**: `tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne` (all spending paths use this address)

**On-Chain Transaction TXIDs:**
- Hash Lock Path: `1ba4835fca1c94e7eb0016ce37c6de2545d07d84a97436f8db999f33a6fd6845`
- Multisig Path: `1951a3be0f05df377b1789223f6da66ed39c781aaf39ace0bf98c3beb7e604a1`
- CSV Timelock Path: `98361ab2c19aa0063f7572cfd0f66cb890b403d2dd12029426613b40d17f41ee`
- Simple Signature Path: `1af46d4c71e121783c3c7195f4b45025a1f38b73fc8898d2546fc33b4c6c71b9`
- Key Path: `1e518aa540bc770df549ec9836d89783ca19fc79b84e7407a882cbe9e95600da`

**Note**: All scripts are configured to reproduce the exact on-chain transactions, including matching output addresses, nSequence values (0xfffffffd for RBF-enabled transactions, 0x02 for CSV), and input/output amounts.

## Common Issues

### Multisig Signature Order
- **Correct**: `[sig_bob, sig_alice, script, control_block]`
- **Wrong**: `[sig_alice, sig_bob, script, control_block]`
- Bob's signature is consumed second, so it must be first in witness stack

### CSV Sequence Value
- Must set sequence in both script and transaction input
- Use `seq.for_script()` in script
- Use `seq.for_input_sequence()` in TxInput

### Control Block Size
- Four-leaf: 97 bytes
- If size is wrong, check script tree structure

### Output Address Consistency
- All spending scripts use the same output address: `tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne`
- This matches the on-chain transactions and ensures TXID reproducibility

### nSequence Values
- Most transactions use `0xfffffffd` (RBF enabled) to match on-chain transactions
- CSV Timelock uses `0x02` (relative blocks = 2) for the timelock
- Incorrect nSequence values will result in different TXIDs

## References

- Chapter 8: Four-Leaf Taproot Script Tree - Complete Implementation of Enterprise-Grade Multi-Path Spending
- BIP 341: Taproot (SegWit version 1 spending rules)
- BIP 340: Schnorr Signatures for secp256k1
- BIP 342: Validation of Taproot Scripts

