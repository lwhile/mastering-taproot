#!/usr/bin/env python3
"""
Chapter 8: Key Path Spending (Maximum Privacy)
Spend from four-leaf Taproot address using Key Path (Alice's internal key)

Based on transaction: 1e518aa540bc770df549ec9836d89783ca19fc79b84e7407a882cbe9e95600da
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2trAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, TxWitnessInput, Sequence
from bitcoinutils.utils import to_satoshis
from bitcoinutils.constants import TYPE_RELATIVE_TIMELOCK
import hashlib
import struct


def key_path_spending():
    """Key Path: Most efficient and private spending method"""
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
    previous_txid = "42a9796a91cf971093b35685db9cb1a164fb5402aa7e2541ea7693acc1923059"
    vout = 0
    input_amount = 0.00002000  # 2000 satoshis
    output_amount = 0.00000888  # 888 satoshis

    # Build transaction
    txin = TxInput(previous_txid, vout)
    txin.sequence = struct.pack('<I', 0xfffffffd)  # RBF enabled
    
    # Use fixed output address from actual on-chain transaction
    output_address = P2trAddress('tb1p060z97qusuxe7w6h8z0l9kam5kn76jur22ecel75wjlmnkpxtnls6vdgne')
    txout = TxOutput(to_satoshis(output_amount), output_address.to_script_pub_key())
    tx = Transaction([txin], [txout], has_segwit=True)

    # Key: Key Path signature (note script_path=False)
    sig_alice = alice_priv.sign_taproot_input(
        tx, 0, [taproot_address.to_script_pub_key()], [to_satoshis(input_amount)],
        script_path=False,      # Key Path mode
        tapleaf_scripts=tree    # Complete script tree (for tweak calculation)
    )

    # Witness data: Only one signature (most efficient!)
    tx.witnesses.append(TxWitnessInput([sig_alice]))

    print("=" * 70)
    print("KEY PATH SPENDING (MAXIMUM PRIVACY)")
    print("=" * 70)
    print(f"\nTransaction Setup:")
    print(f"  Previous TXID: {previous_txid}")
    print(f"  Input Amount: {input_amount} BTC ({to_satoshis(input_amount)} satoshis)")
    print(f"  Output Amount: {output_amount} BTC ({to_satoshis(output_amount)} satoshis)")
    print(f"  Output Address: {output_address.to_string()}")

    print(f"\nKey Path Characteristics:")
    print(f"  - Maximum privacy: No script information revealed")
    print(f"  - Most efficient: Only 64-byte signature in witness")
    print(f"  - Indistinguishable from simple Taproot payment")
    print(f"  - Uses Alice's tweaked private key")

    print(f"\nWitness Data:")
    print(f"  [0] Alice Signature: {sig_alice}")
    print(f"  Note: Only one signature needed (vs 3+ elements for Script Path)")

    print(f"\nTransaction Details:")
    print(f"  Transaction ID: {tx.get_txid()}")
    print("\n" + "=" * 70)

    return tx


if __name__ == "__main__":
    tx = key_path_spending()

