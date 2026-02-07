#!/usr/bin/env python3
"""
Chapter 8: CSV Timelock Script Path Spending
Spend from four-leaf Taproot address using CSV Timelock script (index 2)

Based on transaction: 98361ab2c19aa0063f7572cfd0f66cb890b403d2dd12029426613b40d17f41ee
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2trAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput, Sequence
from bitcoinutils.utils import to_satoshis, ControlBlock
from bitcoinutils.constants import TYPE_RELATIVE_TIMELOCK
import hashlib
import struct


def csv_timelock_path_spending():
    """Script 2: CSV Timelock spending"""
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
    previous_txid = "9a2bff4161411f25675c730777c7b4f5b2837e19898500628f2010c1610ac345"
    vout = 0
    input_amount = 0.00001600  # 1600 satoshis
    output_amount = 0.00000800  # 800 satoshis

    # Key: CSV requires special sequence value (0x02 for 2 blocks)
    seq_for_input = seq.for_input_sequence()

    # Build transaction (note sequence parameter)
    txin = TxInput(previous_txid, vout, sequence=seq_for_input)
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Control Block (script index 2)
    cb = ControlBlock(alice_pub, tree, 2, is_odd=taproot_address.is_odd())

    # Bob signature
    sig_bob = bob_priv.sign_taproot_input(
        tx, 0, [taproot_address.to_script_pub_key()], [to_satoshis(input_amount)],
        script_path=True,
        tapleaf_script=script2,
        tweak=False
    )

    # Witness data: [Bob signature, script, control_block]
    tx.witnesses.append(TxWitnessInput([
        sig_bob,
        script2.to_hex(),
        cb.to_hex()
    ]))

    print("=" * 70)
    print("CSV TIMELOCK SCRIPT PATH SPENDING")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nCSV Timelock Script (Script 2):")
    print(f"  Relative Blocks: {relative_blocks}")
    print(f"  Sequence Value: {seq_for_input.hex()}")
    print(f"  Script Hex: {script2.to_hex()}")

    print(f"\nControl Block (Script 2, CSV Timelock):")
    print(f"  Control Block Hex: {cb.to_hex()}")
    print(f"  Size: {len(bytes.fromhex(cb.to_hex()))} bytes (97 bytes for four-leaf)")

    print(f"\nWitness Data:")
    print(f"  [0] Bob Signature: {sig_bob}")
    print(f"  [1] Script: {script2.to_hex()}")
    print(f"  [2] Control Block: {cb.to_hex()}")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = csv_timelock_path_spending()

