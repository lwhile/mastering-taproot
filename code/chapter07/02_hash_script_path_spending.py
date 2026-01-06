#!/usr/bin/env python3
"""
Chapter 7: Hash Script Path Spending
Spend from dual-leaf Taproot address using Hash Lock script (index 0)

This script demonstrates Script Path spending using the Hash Lock script.
The witness contains: [preimage, script, control_block]

Based on transaction: b61857a05852482c9d5ffbb8159fc2ba1efa3dd16fe4595f121fc35878a2e430
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2trAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.utils import to_satoshis, ControlBlock
import hashlib
import struct


def build_hash_lock_script(preimage):
    """Build Hash Lock Script - verify preimage"""
    preimage_hash = hashlib.sha256(preimage.encode('utf-8')).hexdigest()
    return Script([
        'OP_SHA256',
        preimage_hash,
        'OP_EQUALVERIFY',
        'OP_TRUE'
    ])


def build_bob_script(bob_public):
    """Build Bob Script - P2PK verify Bob's signature"""
    return Script([
        bob_public.to_x_only_hex(),
        'OP_CHECKSIG'
    ])


def hash_script_path_spending():
    """Hash Script Path spending - unlock using preimage"""
    setup('testnet')

    # Rebuild identical script tree
    alice_private = PrivateKey('cRxebG1hY6vVgS9CSLNaEbEJaXkpZvc6nFeqqGT7v6gcW7MbzKNT')
    alice_public = alice_private.get_public_key()

    bob_private = PrivateKey('cSNdLFDf3wjx1rswNL2jKykbVkC6o56o5nYZi4FUkWKjFn2Q5DSG')
    bob_public = bob_private.get_public_key()

    # Build same script tree
    preimage = "helloworld"
    hash_script = build_hash_lock_script(preimage)
    bob_script = build_bob_script(bob_public)

    all_leafs = [hash_script, bob_script]
    taproot_address = alice_public.get_taproot_address(all_leafs)

    # Build transaction
    # Input TXID from actual on-chain transaction: f02c055369812944390ca6a232190ec0db83e4b1b623c452a269408bf8282d66
    # This transaction funded tb1p93c4... with 1,234 sats
    previous_txid = "f02c055369812944390ca6a232190ec0db83e4b1b623c452a269408bf8282d66"
    input_amount = 0.00001234  # 1,234 sats from actual on-chain transaction
    output_amount = 0.00001034  # 1,034 sats (200 sats fee)

    txin = TxInput(previous_txid, 0)  # vout 0 (first output to tb1p93c4...)
    # Set nSequence to 0xffffffff (disable RBF) to match on-chain transaction
    txin.sequence = struct.pack('<I', 0xffffffff)
    
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Key: Build Hash Script's Control Block (index 0)
    control_block = ControlBlock(
        alice_public,
        all_leafs,
        0,  # hash_script index
        is_odd=taproot_address.is_odd()
    )

    # Witness data: [preimage, script, control_block]
    preimage_hex = preimage.encode('utf-8').hex()

    script_path_witness = TxWitnessInput([
        preimage_hex,
        hash_script.to_hex(),
        control_block.to_hex()
    ])

    tx.witnesses.append(script_path_witness)

    print("=" * 70)
    print("HASH SCRIPT PATH SPENDING")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nScript Tree:")
    print(f"  Hash Script (index 0): {hash_script.to_hex()}")
    print(f"  Bob Script (index 1): {bob_script.to_hex()}")

    print(f"\nControl Block (Hash Script, index 0):")
    print(f"  Control Block Hex: {control_block.to_hex()}")
    print(f"  Structure: [version+parity] + [internal_pubkey] + [sibling_hash]")
    print(f"  Size: {len(bytes.fromhex(control_block.to_hex()))} bytes (65 bytes for dual-leaf)")

    print(f"\nWitness Data:")
    print(f"  [0] Preimage: {preimage_hex}")
    print(f"  [1] Script: {hash_script.to_hex()}")
    print(f"  [2] Control Block: {control_block.to_hex()}")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = hash_script_path_spending()

