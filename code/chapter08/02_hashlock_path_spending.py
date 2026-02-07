#!/usr/bin/env python3
"""
Chapter 8: Hash Lock Script Path Spending
Spend from four-leaf Taproot address using Hash Lock script (index 0)

Based on transaction: 1ba4835fca1c94e7eb0016ce37c6de2545d07d84a97436f8db999f33a6fd6845
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2trAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput
from bitcoinutils.utils import to_satoshis, ControlBlock
import hashlib
import struct


def hashlock_path_spending():
    """Script 0: SHA256 Hashlock spending"""
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
    previous_txid = "245563c5aa4c6d32fc34eed2f182b5ed76892d13370f067dc56f34616b66c468"
    vout = 0
    input_amount = 0.00001200  # 1200 satoshis
    output_amount = 0.00000666  # 666 satoshis

    # Build transaction
    txin = TxInput(previous_txid, vout)
    txin.sequence = struct.pack('<I', 0xfffffffd)  # RBF enabled
    
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Key: Construct Control Block (script index 0)
    cb = ControlBlock(alice_pub, tree, 0, is_odd=taproot_address.is_odd())

    # Witness data: [preimage, script, control_block]
    preimage_hex = preimage.encode('utf-8').hex()
    tx.witnesses.append(TxWitnessInput([
        preimage_hex,
        script0.to_hex(),
        cb.to_hex()
    ]))

    print("=" * 70)
    print("HASH LOCK SCRIPT PATH SPENDING")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nControl Block (Script 0, Hash Lock):")
    print(f"  Control Block Hex: {cb.to_hex()}")
    print(f"  Size: {len(bytes.fromhex(cb.to_hex()))} bytes (97 bytes for four-leaf)")

    print(f"\nWitness Data:")
    print(f"  [0] Preimage: {preimage_hex}")
    print(f"  [1] Script: {script0.to_hex()}")
    print(f"  [2] Control Block: {cb.to_hex()}")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = hashlock_path_spending()

