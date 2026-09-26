# ADR-0005: PWQ role-threshold authorization

Status: Accepted
Date: 2026-09-21

## Decision

PWQ approval is a policy-evaluated set of version-bound attestations, not a
single mutable checkbox. A proposal declares eligible signer identities and
roles, a threshold, required roles, distinct-signer enforcement, allowed proof
types, and an optional exact action/resource scope. Every attestation binds the
canonical digest of that proposal id, version, and normalized content.

The canonical writer mints `dispatch_authorization` only when the current
attestation set satisfies both the threshold and every required role. Modifying
the card changes its digest and revokes the complete attestation set, prior
authorization, and execution tracker.

Ordinary PWQ work retains a compatible 1-of-1 human-owner policy. Sensitive
runtime activation uses 2-of-2 split control:

1. `human_owner` decides whether the intent and scope are approved.
2. `runtime_guardian` attests that the exact immutable candidate passed fixed,
   non-executing validation and names the still-active rollback parent.

The guardian's evidence is necessary but is not human consent. Iter remains the
proposer/executor and is eligible for neither approval role.

## Proof boundary and future on-chain use

The first implementation accepts only verified protocol adapters:
`trusted_local_session_v1` at the Electron human boundary and
`hotload_validation_v1` in the non-self-modifiable recovery control plane. These
are local attestations, not claims of wallet key custody or blockchain
settlement. A proof label such as EIP-712 is rejected until a real verifier is
installed.

Future wallet, hardware-wallet, contract-wallet, DID, or on-chain adapters reuse
the same envelope and proposal digest. They must verify chain/domain separation,
signer identity, nonce/replay rules, and finality before their proof type becomes
eligible. That extension does not change the PWQ state machine or allow a
technical witness to become the human decision maker.

## Consequences

- Sensitive dispatch has explicit separation of decision and technical-witness roles.
- Partial approval never produces a dispatch token.
- Signatures cannot be replayed across proposal versions or candidates.
- Existing ordinary cards and legacy approval events remain readable.
- The event ledger and board expose who attested, in what role, against which digest, and with which verified proof type.
