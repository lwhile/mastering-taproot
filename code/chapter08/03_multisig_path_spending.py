#!/usr/bin/env python3
"""
Chapter 8: 2-of-2 Multisig Script Path Spending
Spend from four-leaf Taproot address using Multisig script (index 1)

Based on transaction: 1951a3be0f05df377b1789223f6da66ed39c781aaf39ace0bf98c3beb7e604a1
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2trAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.utils import to_satoshis, ControlBlock
import hashlib
import struct


def multisig_path_spending():
    """Script 1: 2-of-2 Multisig spending"""
    setup('testnet')

    # Rebuild script tree (must match exactly)
    alice_priv = PrivateKey("cRxebG1hY6vVgS9CSLNaEbEJaXkpZvc6nFeqqGT7v6gcW7MbzKNT")
    bob_priv = PrivateKey("cSNdLFDf3wjx1rswNL2jKykbVkC6o56o5nYZi4FUkWKjFn2Q5DSG")
    alice_pub = alice_priv.get_public_key()
    bob_pub = bob_priv.get_public_key()

    # Rebuild all scripts
    preimage = "helloworld"
    hash0 = hashlib.sha256(preimage.encode('utf-8')).hexdigest()
    script0 = Script(['OP_SHA256', hash0, 'OP_EQUALVERIFY', 'OP_TRUE'])

    script1 = Script([
        "OP_0",
        alice_pub.to_x_only_hex(),
        "OP_CHECKSIGADD",
        bob_pub.to_x_only_hex(),
        "OP_CHECKSIGADD",
        "OP_2",
        "OP_EQUAL"
    ])

    from bitcoinutils.transactions import Sequence
    from bitcoinutils.constants import TYPE_RELATIVE_TIMELOCK
    relative_blocks = 2
    seq = Sequence(TYPE_RELATIVE_TIMELOCK, relative_blocks)
    script2 = Script([
        seq.for_script(),
        "OP_CHECKSEQUENCEVERIFY",
        "OP_DROP",
        bob_pub.to_x_only_hex(),
        "OP_CHECKSIG"
    ])

    script3 = Script([bob_pub.to_x_only_hex(), "OP_CHECKSIG"])

    tree = [[script0, script1], [script2, script3]]
    taproot_address = alice_pub.get_taproot_address(tree)

    # UTXO information
    # Input TXID from actual on-chain transaction
    previous_txid = "1ed5a3e97a6d3bc0493acc2aac15011cd99000b52e932724766c3d277d76daac"
    vout = 0
    input_amount = 0.00001400  # 1400 satoshis
    output_amount = 0.00000668  # 668 satoshis

    # Build transaction
    txin = TxInput(previous_txid, vout)
    # Set nSequence to 0xfffffffd (RBF enabled) to match on-chain transaction
    txin.sequence = struct.pack('<I', 0xfffffffd)
    
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Key: Construct Control Block (script index 1)
    cb = ControlBlock(alice_pub, tree, 1, is_odd=taproot_address.is_odd())

    # Key: Script Path signature (note script_path=True)
    sig_alice = alice_priv.sign_taproot_input(
        tx, 0, [taproot_address.to_script_pub_key()], [to_satoshis(input_amount)],
        script_path=True,
        tapleaf_script=script1,
        tweak=False
    )

    sig_bob = bob_priv.sign_taproot_input(
        tx, 0, [taproot_address.to_script_pub_key()], [to_satoshis(input_amount)],
        script_path=True,
        tapleaf_script=script1,
        tweak=False
    )

    # Witness data: [Bob signature, Alice signature, script, control_block]
    # Note: Bob signature first (stack execution order - consumed second)
    tx.witnesses.append(TxWitnessInput([
        sig_bob,               # Consumed second by OP_CHECKSIGADD
        sig_alice,             # Consumed first by OP_CHECKSIGADD
        script1.to_hex(),
        cb.to_hex()
    ]))

    print("=" * 70)
    print("2-OF-2 MULTISIG SCRIPT PATH SPENDING")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nMultisig Script (Script 1):")
    print(f"  Script Hex: {script1.to_hex()}")
    print(f"  Uses OP_CHECKSIGADD (Tapscript style, more efficient)")

    print(f"\nControl Block (Script 1, Multisig):")
    print(f"  Control Block Hex: {cb.to_hex()}")
    print(f"  Size: {len(bytes.fromhex(cb.to_hex()))} bytes (97 bytes for four-leaf)")

    print(f"\nWitness Data:")
    print(f"  [0] Bob Signature: {sig_bob}")
    print(f"  [1] Alice Signature: {sig_alice}")
    print(f"  [2] Script: {script1.to_hex()}")
    print(f"  [3] Control Block: {cb.to_hex()}")
    print(f"  Note: Bob sig first, but consumed second by OP_CHECKSIGADD")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = multisig_path_spending()

