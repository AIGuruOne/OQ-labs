---
kb_id: KB-007
title: GateKey VPN will not connect
category: network
routing_queue: network_ops
systems: GateKey VPN, KeyNest
updated: 2026-09-29
---

# GateKey VPN will not connect

## Symptom
**GateKey VPN** fails to connect from outside the office, or connects and then drops within a
minute.

## Check these first, in order
1. **Is the internet working at all?** Open any public website. If nothing loads, the problem is
   the local network, not GateKey.
2. **Is your MFA prompt being answered?** GateKey waits 30 seconds for a **KeyNest** approval and
   then reports a generic failure. A missed prompt looks exactly like a broken VPN.
3. **Hotel and cafe networks** often block the ports GateKey uses. Tethering to a phone is the
   fastest test: if it connects on tethering, the venue network is the cause.
4. **Are you already on the office network?** GateKey refuses to connect from inside, by design.

## Still failing
Raise a ticket to `network_ops` with the error code GateKey shows, the network you are on
(office, home, hotel, tethered) and the time you tried. Without the error code the desk cannot
tell a credential problem from a routing one.

## What the desk will not do
There is no split-tunnel exception and no permanent bypass. Both have been asked for and refused.
