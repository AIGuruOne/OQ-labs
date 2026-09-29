---
kb_id: KB-016
title: A DocHarbor document is locked by someone else
category: software
routing_queue: apps_support
systems: DocHarbor
updated: 2026-09-29
---

# A DocHarbor document is locked by someone else

## Symptom
**DocHarbor** shows a document as checked out or locked by another person, and you cannot edit it.

## What it means
DocHarbor locks a document while somebody has it open for editing, so two people cannot overwrite
each other. The lock is usually real, not a fault.

## Steps
1. DocHarbor names the person holding the lock. Ask them to close it - this resolves most cases in
   minutes.
2. If they are on leave or have left, raise a ticket to `apps_support` with the document reference
   and the name shown.
3. The desk can force-release a lock. It does this only after confirming with the document owner,
   because a forced release discards whatever the other person had unsaved.

## Locks that never clear
A lock held by a session that crashed clears itself after eight hours. If a document is still
locked the next working day with nobody editing it, that is worth a ticket.
