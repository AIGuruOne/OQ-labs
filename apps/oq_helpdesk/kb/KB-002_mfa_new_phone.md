---
kb_id: KB-002
title: Moving multi-factor authentication to a new phone
category: access
routing_queue: identity_access
systems: KeyNest, MyPortal
updated: 2026-09-29
---

# Moving multi-factor authentication to a new phone

## Symptom
You have a new phone and **KeyNest** still asks for a code from the old one, or the old device is
gone and you cannot get a code at all.

## Do this before you wipe the old phone
While you still have both phones, open KeyNest on the old one, choose *Add a device*, and scan the
code shown on the new one. This takes two minutes and avoids everything below.

## If the old phone is already gone
You cannot re-enrol yourself: the desk must clear the old enrolment first.
1. Raise a ticket to `identity_access` titled "MFA re-enrolment".
2. State your staff number and the site you are at.
3. A desk agent clears the old device and calls you back on the number in **StaffGate**, not on
   the number in the ticket. Make sure StaffGate is current.
4. You then enrol the new phone from the KeyNest sign-in screen.

## What the desk cannot do
The desk cannot read you a code and cannot disable MFA, not even temporarily. Anyone offering to
do either is not from the desk - report it to `security_ops`.
