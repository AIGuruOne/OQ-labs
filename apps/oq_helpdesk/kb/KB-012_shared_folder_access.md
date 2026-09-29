---
kb_id: KB-012
title: Access to a folder on the S: drive
category: access
routing_queue: identity_access
systems: S: drive, StaffGate
updated: 2026-09-29
---

# Access to a folder on the S: drive

## Symptom
A folder on the `S: drive` is refused, or a colleague's link opens an access-denied page.

## Folders have owners, not administrators
Every top-level folder on the `S: drive` has a named business owner. The desk grants access on
that owner's approval and never on its own judgement, even for a manager.

## Steps
1. Get the full path, starting `S:\`. A screenshot of the error is not enough - the desk needs
   the path.
2. Raise a StaffGate request for *Shared folder access* and paste the path.
3. StaffGate looks up the owner and routes the approval. If the owner has left and no successor is
   recorded, the request stalls - say so in the ticket and `identity_access` will find the owner.

## Read or write
Ask for the one you need. Write access to a folder you only read from is another access-review
finding, and it is granted for the life of your role, not the life of the task.
