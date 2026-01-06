#!/usr/bin/env python3
"""
Chapter 7: Create Dual-Leaf Taproot Address
Build a dual-leaf script tree containing Hash Lock and Bob Script

This script demonstrates the Commit Phase for dual-leaf Taproot:
- Script 1: Hash Lock (anyone with preimage "helloworld" can spend)
- Script 2: Bob Script (only Bob's private key holder can spend)
- Key Path: Alice can spend directly (maximum privacy)

Expected output address: tb1p93c4wxsr87p88jau7vru83zpk6xl0shf5ynmutd9x0gxwau3tngq9a4w3z
"""

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey
from bitcoinutils.script import Script
import hashlib


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


def create_dual_leaf_taproot():
    """Build dual-leaf Taproot address containing Hash Lock and Bob Script"""
    setup('testnet')

    # Alice's internal key (Key Path controller)
    alice_private = PrivateKey('cRxebG1hY6vVgS9CSLNaEbEJaXkpZvc6nFeqqGT7v6gcW7MbzKNT')
    alice_public = alice_private.get_public_key()

    # Bob's key (Script Path 2 controller)
    bob_private = PrivateKey('cSNdLFDf3wjx1rswNL2jKykbVkC6o56o5nYZi4FUkWKjFn2Q5DSG')
    bob_public = bob_private.get_public_key()

    # Script 1: Hash Lock - verify preimage "helloworld"
    preimage = "helloworld"
    hash_script = build_hash_lock_script(preimage)

    # Script 2: Bob Script - P2PK verify Bob's signature
    bob_script = build_bob_script(bob_public)

    # Build dual-leaf script tree (flat structure)
    all_leafs = [hash_script, bob_script]

    # Generate Taproot address
    taproot_address = alice_public.get_taproot_address(all_leafs)

    print("=" * 70)
    print("DUAL-LEAF TAPROOT ADDRESS CREATION")
    print("=" * 70)
    print(f"\nAlice's Internal Key:")
    print(f"  Private Key (WIF): {alice_private.to_wif()}")
    print(f"  Public Key: {alice_public.to_hex()}")
    print(f"  X-only Pubkey: {alice_public.to_x_only_hex()}")

    print(f"\nBob's Key:")
    print(f"  Private Key (WIF): {bob_private.to_wif()}")
    print(f"  Public Key: {bob_public.to_hex()}")
    print(f"  X-only Pubkey: {bob_public.to_x_only_hex()}")

    print(f"\nScript 1: Hash Lock Script")
    print(f"  Preimage: '{preimage}'")
    print(f"  Preimage Hash: {hashlib.sha256(preimage.encode('utf-8')).hexdigest()}")
    print(f"  Script Hex: {hash_script.to_hex()}")
    print(f"  Script Index: 0")

    print(f"\nScript 2: Bob Script (P2PK)")
    print(f"  Bob's X-only Pubkey: {bob_public.to_x_only_hex()}")
    print(f"  Script Hex: {bob_script.to_hex()}")
    print(f"  Script Index: 1")

    print(f"\nDual-Leaf Script Tree:")
    print(f"  Structure: [Hash Script (index 0), Bob Script (index 1)]")
    print(f"  Total Leaves: {len(all_leafs)}")

    print(f"\nGenerated Taproot Address:")
    print(f"  Address: {taproot_address.to_string()}")

    print(f"\nSpending Paths:")
    print(f"  1. Key Path: Alice can spend directly using internal key (maximum privacy)")
    print(f"  2. Script Path 0: Hash Script - anyone with preimage 'helloworld' can spend")
    print(f"  3. Script Path 1: Bob Script - only Bob's private key holder can spend")

    print("\n" + "=" * 70)

    return taproot_address, hash_script, bob_script, alice_private, bob_private


if __name__ == "__main__":
    taproot_address, hash_script, bob_script, alice_private, bob_private = create_dual_leaf_taproot()

