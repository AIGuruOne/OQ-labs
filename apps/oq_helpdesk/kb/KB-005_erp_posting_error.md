---
kb_id: KB-005
title: Tavrona ERP rejects a posting with a period error
category: erp
routing_queue: erp_support
systems: Tavrona ERP
updated: 2026-09-29
---

# Tavrona ERP rejects a posting with a period error

## Symptom
A posting in **Tavrona ERP** is refused with a message about a closed or not-open period.

## What it means
The accounting period you are posting into is closed. This is a control, not a fault: finance
closes periods deliberately and reopening one is a finance decision, not a desk decision.

## What to do
1. Check the document date. Most of these are a typo in the year or month.
2. If the date is right and the period really is closed, the posting has to move to the open
   period or finance has to reopen the old one.
3. Raise a ticket to `erp_support` with the document number and the exact message. The desk routes
   it to finance; the desk cannot reopen a period itself.

## What not to do
Do not change the date to force the posting through. It will reconcile wrongly later and the
correction is far more work than the delay.
