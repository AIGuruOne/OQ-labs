---
kb_id: KB-020
title: VoxLine desk phone or softphone has no dial tone
category: telecom
routing_queue: telecom_voice
systems: VoxLine
updated: 2026-09-29
---

# VoxLine desk phone or softphone has no dial tone

## Symptom
A **VoxLine** desk phone shows no line, or the softphone says *not registered*.

## Steps
1. If it is a desk phone, unplug the network cable and plug it back in. VoxLine phones re-register
   in about 40 seconds; wait the full time before concluding anything.
2. If it is the softphone, sign out and in. The registration token expires every seven days and an
   expired token reports itself as a network fault.
3. Check whether the handset works in a neighbouring desk socket. That separates the phone from
   the socket in one move.

## What to include in the ticket
Raise to `telecom_voice` with your extension number, the site code, and whether the handset worked
in another socket. An extension number is essential - the desk cannot search VoxLine by name.

## Call forwarding and voicemail
Both are self-service in VoxLine under *My line*. The desk does not set them up for you, and a
request to do so comes back with a link to this article.
