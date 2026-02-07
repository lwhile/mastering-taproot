#!/usr/bin/env python3
"""
Chapter 8: Create Four-Leaf Taproot Address
Build a four-leaf script tree containing:
- Script 0: SHA256 Hash Lock
- Script 1: 2-of-2 Multisig (Tapscript style with OP_CHECKSIGADD)
- Script 2: CSV Timelock
- Script 3: Simple Signature

Expected output address: tb1pjfdm902y2adr08qnn4tahxjvp6x5selgmvzx63yfqk2hdey02yvqjcr29q
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.script import Script
from bitcoinutils.transactions import Sequence
from bitcoinutils.constants import TYPE_RELATIVE_TIMELOCK
import hashlib


def create_four_leaf_taproot():
    """Build four-leaf Taproot address with Hash Lock, Multisig, CSV, and Simple Signature"""
    setup('testnet')

    # Generate participant keys
    # Note: Using known working keys from previous chapters
    alice_priv = PrivateKey("cRxebG1hY6vVgS9CSLNaEbEJaXkpZvc6nFeqqGT7v6gcW7MbzKNT")
    bob_priv = PrivateKey("cSNdLFDf3wjx1rswNL2jKykbVkC6o56o5nYZi4FUkWKjFn2Q5DSG")
    alice_pub = alice_priv.get_public_key()
    bob_pub = bob_priv.get_public_key()

    # Script 0: SHA256 Hashlock
    preimage = "helloworld"
    hash0 = hashlib.sha256(preimage.encode('utf-8')).hexdigest()
    script0 = Script([
        'OP_SHA256',
        hash0,
        'OP_EQUALVERIFY',
        'OP_TRUE'
    ])

    # Script 1: 2-of-2 Multisig (Tapscript style)
    script1 = Script([
        "OP_0",                      # Initialize counter
        alice_pub.to_x_only_hex(),   # Alice's x-only public key
        "OP_CHECKSIGADD",           # Verify Alice signature, increment counter
        bob_pub.to_x_only_hex(),    # Bob's x-only public key
        "OP_CHECKSIGADD",           # Verify Bob signature, increment counter
        "OP_2",                     # Required signature count
        "OP_EQUAL"                  # Check counter == required count
    ])

    # Script 2: CSV Timelock
    relative_blocks = 2
    seq = Sequence(TYPE_RELATIVE_TIMELOCK, relative_blocks)
    script2 = Script([
        seq.for_script(),           # Push sequence value
        "OP_CHECKSEQUENCEVERIFY",   # Verify relative timelock
        "OP_DROP",                  # Clean stack
        bob_pub.to_x_only_hex(),    # Bob's public key
        "OP_CHECKSIG"               # Verify Bob's signature
    ])

    # Script 3: Simple Signature
    script3 = Script([
        bob_pub.to_x_only_hex(),
        "OP_CHECKSIG"
    ])

    # Build script tree: [[left branch], [right branch]]
    # Left branch: [script0, script1]
    # Right branch: [script2, script3]
    tree = [[script0, script1], [script2, script3]]

    # Generate Taproot address using Alice's internal key
    taproot_address = alice_pub.get_taproot_address(tree)

    print("=" * 70)
    print("FOUR-LEAF TAPROOT ADDRESS CREATION")
    print("=" * 70)
    print(f"\nAlice's Internal Key:")
    print(f"  Private Key (WIF): {alice_priv.to_wif()}")
    print(f"  Public Key: {alice_pub.to_hex()}")
    print(f"  X-only Pubkey: {alice_pub.to_x_only_hex()}")

    print(f"\nBob's Key:")
    print(f"  Private Key (WIF): {bob_priv.to_wif()}")
    print(f"  Public Key: {bob_pub.to_hex()}")
    print(f"  X-only Pubkey: {bob_pub.to_x_only_hex()}")

    print(f"\nScript 0: SHA256 Hash Lock")
    print(f"  Preimage: '{preimage}'")
    print(f"  Preimage Hash: {hash0}")
    print(f"  Script Hex: {script0.to_hex()}")
    print(f"  Script Index: 0")

    print(f"\nScript 1: 2-of-2 Multisig (Tapscript)")
    print(f"  Alice Pubkey: {alice_pub.to_x_only_hex()}")
    print(f"  Bob Pubkey: {bob_pub.to_x_only_hex()}")
    print(f"  Script Hex: {script1.to_hex()}")
    print(f"  Script Index: 1")
    print(f"  Note: Uses OP_CHECKSIGADD (more efficient than OP_CHECKMULTISIG)")

    print(f"\nScript 2: CSV Timelock")
    print(f"  Relative Blocks: {relative_blocks}")
    print(f"  Bob Pubkey: {bob_pub.to_x_only_hex()}")
    print(f"  Script Hex: {script2.to_hex()}")
    print(f"  Script Index: 2")

    print(f"\nScript 3: Simple Signature")
    print(f"  Bob Pubkey: {bob_pub.to_x_only_hex()}")
    print(f"  Script Hex: {script3.to_hex()}")
    print(f"  Script Index: 3")

    print(f"\nFour-Leaf Script Tree Structure:")
    print(f"  Merkle Root")
    print(f"    /            \\")
    print(f"  Branch0      Branch1")
    print(f"  /      \\     /      \\")
    print(f" Script0 Script1 Script2 Script3")
    print(f" (Hash)  (Multi) (CSV)   (Sig)")
    print(f"  Tree: {tree}")

    print(f"\nGenerated Taproot Address:")
    print(f"  Address: {taproot_address.to_string()}")

    print(f"\nSpending Paths:")
    print(f"  1. Key Path: Alice can spend directly using internal key (maximum privacy)")
    print(f"  2. Script Path 0: Hash Lock - anyone with preimage 'helloworld' can spend")
    print(f"  3. Script Path 1: 2-of-2 Multisig - requires both Alice and Bob signatures")
    print(f"  4. Script Path 2: CSV Timelock - Bob can spend after 2 blocks")
    print(f"  5. Script Path 3: Simple Signature - Bob can spend immediately")

    print("\n" + "=" * 70)

    return taproot_address, tree, script0, script1, script2, script3, alice_priv, bob_priv, alice_pub, bob_pub


if __name__ == "__main__":
    taproot_address, tree, script0, script1, script2, script3, alice_priv, bob_priv, alice_pub, bob_pub = create_four_leaf_taproot()

