# StreetKingz AI Content Engine

## Purpose

StreetKingz AI Content Engine is a local AI-powered content production system designed to reduce the time required to plan, organise and produce social media content.

The system takes raw video footage, automatically categorises it, builds a searchable content library, identifies missing footage, generates content plans and creates edit packs.

The goal is to remove as much planning and organisation work as possible so the user can focus on filming, editing and posting.

---

## Current Workflow

1. Film content
2. Place raw clips into Inbox
3. Analyse Inbox
4. AI categorises clips
5. Clips are moved into B-Roll library
6. Metadata is stored in master database
7. Health Check identifies content gaps
8. Weekly Content Generator creates posting plan
9. Edit Packs gather required clips
10. User edits and publishes

---

## Core Features

### Inbox Analysis

Analyses clips using OpenAI Vision.

Outputs:

* Category
* Story role
* Shot type
* Confidence score
* Tags
* Suggested usage

Clips are either:

* Filed into the content library
* Sent to Quarantine

General category clips currently require manual review.

---

### Content Library

Master database:

street_kingz_master_clip_database.csv

Stores all analysed clip metadata.

Used by every other system component.

---

### Health Check

Measures content coverage by category.

Current categories:

* Wheels
* Drying
* Foam
* Glass
* Interior

Outputs:

* Coverage score
* Missing footage
* Filming priorities

---

### Weekly Content Generator

Creates a 7-day content plan.

Uses:

* Available clips
* Voice library
* Campaign brief
* Product focus

Outputs:

* Hooks
* Voiceovers
* Captions
* CTA
* Clip sequences
* Missing footage requirements

---

### Edit Packs

Creates folders containing all clips required for a video.

Supports:

* Single video pack
* Entire weekly plan pack

---

## Long-Term Vision

Become a creator operating system.

Potential future features:

* Product launch planning
* Content gap forecasting
* Single video generator
* Progress tracking
* Multi-platform support
* Cloud sync
* SaaS version

The system should remain creator-focused and practical.

Avoid adding complexity that does not reduce workload.
