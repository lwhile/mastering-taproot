#!/usr/bin/env python3
"""
Chapter 7: Bob Script Path Spending
Spend from dual-leaf Taproot address using Bob Script (index 1)

This script demonstrates Script Path spending using Bob's P2PK script.
The witness contains: [signature, script, control_block]

Based on transaction: 185024daff64cea4c82f129aa9a8e97b4622899961452d1d144604e65a70cfe0
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


def bob_script_path_spending():
    """Bob Script Path spending - unlock using Bob's private key signature"""
    setup('testnet')

    # Same script tree construction
    alice_private = PrivateKey('cRxebG1hY6vVgS9CSLNaEbEJaXkpZvc6nFeqqGT7v6gcW7MbzKNT')
    alice_public = alice_private.get_public_key()

    bob_private = PrivateKey('cSNdLFDf3wjx1rswNL2jKykbVkC6o56o5nYZi4FUkWKjFn2Q5DSG')
    bob_public = bob_private.get_public_key()

    # Rebuild script tree
    preimage_hash = hashlib.sha256("helloworld".encode('utf-8')).hexdigest()
    hash_script = Script(['OP_SHA256', preimage_hash, 'OP_EQUALVERIFY', 'OP_TRUE'])
    bob_script = build_bob_script(bob_public)

    all_leafs = [hash_script, bob_script]
    taproot_address = alice_public.get_taproot_address(all_leafs)

    # Build transaction
    # Input TXID from actual on-chain transaction: 8caddfad76a5b3a8595a522e24305dc20580ca868ef733493e308ada084a050c
    # This transaction funded tb1p93c4... with 1,111 sats (second output, vout 1)
    previous_txid = "8caddfad76a5b3a8595a522e24305dc20580ca868ef733493e308ada084a050c"
    input_amount = 0.00001111  # 1,111 sats from actual on-chain transaction
    output_amount = 0.00000900  # 900 sats (211 sats fee)

    txin = TxInput(previous_txid, 1)  # vout 1 (second output to tb1p93c4...)
    # Set nSequence to 0xffffffff (disable RBF) to match on-chain transaction
    txin.sequence = struct.pack('<I', 0xffffffff)
    
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1pshzcvake3a3d76jmue3jz4hyh35yvk0gjj752pd53ys9txy5c3aswe5cn7')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Key: Build Bob Script's Control Block (index 1)
    control_block = ControlBlock(
        alice_public,
        all_leafs,
        1,  # bob_script index
        is_odd=taproot_address.is_odd()
    )

    # Script Path signature (note parameters)
    sig = bob_private.sign_taproot_input(
        tx, 0,
        [taproot_address.to_script_pub_key()],
        [to_satoshis(input_amount)],
        script_path=True,
        tapleaf_script=bob_script,  # Singular form!
        tweak=False
    )

    # Witness data: [signature, script, control_block]
    script_path_witness = TxWitnessInput([
        sig,
        bob_script.to_hex(),
        control_block.to_hex()
    ])

    tx.witnesses.append(script_path_witness)

    print("=" * 70)
    print("BOB SCRIPT PATH SPENDING")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Vout: 1")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nScript Tree:")
    print(f"  Hash Script (index 0): {hash_script.to_hex()}")
    print(f"  Bob Script (index 1): {bob_script.to_hex()}")

    print(f"\nControl Block (Bob Script, index 1):")
    print(f"  Control Block Hex: {control_block.to_hex()}")
    print(f"  Structure: [version+parity] + [internal_pubkey] + [sibling_hash]")
    print(f"  Size: {len(bytes.fromhex(control_block.to_hex()))} bytes (65 bytes for dual-leaf)")

    print(f"\nWitness Data:")
    print(f"  [0] Signature: {sig}")
    print(f"  [1] Script: {bob_script.to_hex()}")
    print(f"  [2] Control Block: {control_block.to_hex()}")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = bob_script_path_spending()

