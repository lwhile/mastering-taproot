# Chapter 7: Taproot Dual-Leaf Script Tree

This directory contains code examples for Chapter 7, demonstrating the complete implementation of dual-leaf Taproot script trees with Hash Lock and Bob Script.

## Overview

This chapter demonstrates how to build and spend from a dual-leaf Taproot script tree, which contains:
- **Script Path 0**: Hash Lock script (anyone with preimage "helloworld" can spend)
- **Script Path 1**: Bob Script (only Bob's private key holder can spend)
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

### `01_create_dual_leaf_taproot.py`
Creates a dual-leaf Taproot address containing Hash Lock and Bob Script.

**Expected Output:**
- Taproot Address: `tb1p93c4wxsr87p88jau7vru83zpk6xl0shf5ynmutd9x0gxwau3tngq9a4w3z`

**Key Concepts:**
- Flat script tree structure: `[hash_script, bob_script]`
- Script indices: Hash Script = 0, Bob Script = 1
- Same address can be spent via multiple Script Paths

**Run:**
```bash
python3 01_create_dual_leaf_taproot.py
```

### `02_hash_script_path_spending.py`
Implements Hash Script Path spending using the preimage "helloworld".

**Based on Transaction:**
- TXID: `b61857a05852482c9d5ffbb8159fc2ba1efa3dd16fe4595f121fc35878a2e430`
- Input TXID: `f02c055369812944390ca6a232190ec0db83e4b1b623c452a269408bf8282d66`
- Input Amount: 1,234 sats (0.00001234 BTC)
- Output Amount: 1,034 sats (0.00001034 BTC)
- Output Address: `tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne`

**Witness Structure:**
- `[0]`: Preimage hex (`68656c6c6f776f726c64`)
- `[1]`: Hash Script hex
- `[2]`: Control Block (65 bytes: version+parity + internal_pubkey + sibling_hash)

**Key Concepts:**
- Control Block index: 0 (Hash Script)
- Control Block contains Bob Script's TapLeaf hash as sibling proof
- Script execution: OP_SHA256 → hash comparison → OP_TRUE

**Run:**
```bash
python3 02_hash_script_path_spending.py
```

### `03_bob_script_path_spending.py`
Implements Bob Script Path spending using Bob's private key signature.

**Based on Transaction:**
- TXID: `185024daff64cea4c82f129aa9a8e97b4622899961452d1d144604e65a70cfe0`
- Input TXID: `8caddfad76a5b3a8595a522e24305dc20580ca868ef733493e308ada084a050c`
- Input Vout: 1 (second output to tb1p93c4...)
- Input Amount: 1,111 sats (0.00001111 BTC)
- Output Amount: 900 sats (0.00000900 BTC)
- Output Address: `tb1pshzcvake3a3d76jmue3jz4hyh35yvk0gjj752pd53ys9txy5c3aswe5cn7`

**Witness Structure:**
- `[0]`: Bob's Schnorr signature (64 bytes)
- `[1]`: Bob Script hex
- `[2]`: Control Block (65 bytes: version+parity + internal_pubkey + sibling_hash)

**Key Concepts:**
- Control Block index: 1 (Bob Script)
- Control Block contains Hash Script's TapLeaf hash as sibling proof
- Script execution: OP_CHECKSIG verifies Bob's signature
- Script Path signature uses `script_path=True` and `tapleaf_script=bob_script`

**Run:**
```bash
python3 03_bob_script_path_spending.py
```

### `04_verify_control_block.py`
Verifies Control Blocks from both Script Paths and demonstrates address reconstruction.

**Key Concepts:**
- Control Block structure: 65 bytes for dual-leaf (vs 33 bytes for single-leaf)
- Sibling node verification: Each Control Block contains its sibling's TapLeaf hash
- Merkle Root calculation: TapBranch(sorted(TapLeaf_A, TapLeaf_B))
- Address reconstruction: output_key = internal_pubkey + tweak * G

**Run:**
```bash
python3 04_verify_control_block.py
```

## Key Technical Points

### Dual-Leaf vs Single-Leaf

| Aspect | Single-Leaf | Dual-Leaf |
|--------|-------------|-----------|
| **Control Block Size** | 33 bytes | 65 bytes |
| **Merkle Root** | TapLeaf Hash | TapBranch Hash |
| **Merkle Path** | None | Sibling TapLeaf hash |
| **Script Indices** | Always 0 | 0, 1, ... |

### Control Block Structure

**Single-Leaf (33 bytes):**
```
[1 byte: version+parity] + [32 bytes: internal_pubkey]
```

**Dual-Leaf (65 bytes):**
```
[1 byte: version+parity] + [32 bytes: internal_pubkey] + [32 bytes: sibling_hash]
```

### Merkle Tree Calculation

1. Calculate each script's TapLeaf hash:
   ```
   TapLeaf = Tagged_Hash("TapLeaf", 0xc0 + len(script) + script)
   ```

2. Sort TapLeaf hashes lexicographically

3. Calculate Merkle Root:
   ```
   Merkle Root = Tagged_Hash("TapBranch", sorted(TapLeaf_A, TapLeaf_B))
   ```

4. Calculate tweak:
   ```
   Tweak = Tagged_Hash("TapTweak", internal_pubkey + merkle_root)
   ```

5. Generate output key:
   ```
   Output Key = Internal Pubkey + Tweak * G
   ```

## Transaction Verification

Both Script Path transactions use the **same Taproot address**, proving they originate from the same dual-leaf script tree:

- Hash Script Path: `b61857a05852482c9d5ffbb8159fc2ba1efa3dd16fe4595f121fc35878a2e430`
- Bob Script Path: `185024daff64cea4c82f129aa9a8e97b4622899961452d1d144604e65a70cfe0`
- Address: `tb1p93c4wxsr87p88jau7vru83zpk6xl0shf5ynmutd9x0gxwau3tngq9a4w3z`

**Transaction Verification**: ✅ Both transactions have been verified to match on-chain TXIDs exactly!

All transaction parameters have been set to match the actual on-chain transactions:
- Input/output amounts are correct
- Output addresses match the actual transaction outputs
- nSequence values set to 0xffffffff (disable RBF)
- Control Blocks and witness data are correct

## Common Issues

### Script Index Mismatch
- Ensure Control Block index matches the script being used
- Hash Script = index 0, Bob Script = index 1

### Control Block Size
- Single-leaf: 33 bytes
- Dual-leaf: 65 bytes
- If size is wrong, check script tree structure

### Sibling Hash Verification
- Hash Script's Control Block contains Bob Script's TapLeaf hash
- Bob Script's Control Block contains Hash Script's TapLeaf hash
- Verify sibling relationships match

## References

- Chapter 7: Taproot Dual-Leaf Script Tree - Complete Implementation of Hash Lock and Bob Script
- BIP 341: Taproot (SegWit version 1 spending rules)
- BIP 340: Schnorr Signatures for secp256k1

