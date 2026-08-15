# Positioning

*What this site is for, and how to decide what belongs on it.*

Last updated: 15 August 2026

---

## The claim

> There's something interesting here that people aren't seeing.
> Can I build something that makes them see it?

That's the site. Everything on it is evidence for that one sentence.

On the page it reads as the headline:

> **I build small things that change what you notice.**

"Notice" is deliberate, not decorative. It is already the load-bearing verb
across the work — Seasonal's stated goal is *"I started noticing the year,"* The
Local Season is about noticing routines, Must Watch is about what is worth
noticing tonight. Earlier drafts ended on "how you see a familiar one," which
was an abstraction standing in for the real thing.

Shifting perspective is the reason the projects exist. It's not a side effect of
being curious, and it's not a portfolio theme applied after the fact — it's the
actual motive. A project belongs here when it takes something a person already
encounters and makes them notice what was always in it.

## Who this is for

Someone who has just been given the link — a colleague, a recruiter, a founder,
a person who read something and looked me up. They will spend roughly ninety
seconds. They should leave able to describe what I do to someone else.

They should *not* have to click anything to get the idea. The homepage carries
the claim and the evidence together.

## What I want them to come away with

In order of priority:

1. **This person notices things other people walk past, and then builds the
   thing that makes the noticing transferable.**
2. He does this well enough, and often enough, that it's clearly a habit rather
   than a hobby.
3. He's a finance leader — which is where the instinct gets applied at scale, on
   problems with real money attached.

Note the order. The finance credential is what makes the claim *credible*, not
what makes it *interesting*. Leading with it turns the site into a résumé, and a
résumé is exactly what the work is better than.

## What this site is not

- **Not a personal library.** The original build was organized around four
  facets of a person — projects, seasons, quotes, photos. That structure asks
  "who is Brett?" and answers with a list of interests. Wrong question.
- **Not a portfolio of everything.** Volume is not the argument. A project that
  works but doesn't shift perspective dilutes the ones that do.
- **Not a blog.** Writing is welcome when it argues the claim. It is not a
  standing obligation, and an empty writing section costs more than no writing
  section.
- **Not a place to be modest.** "An early attempt," "a work in progress," "a
  rough sketch" — this kind of hedging reads as honesty and functions as
  self-sabotage. Ship it or don't, but don't apologize for it in public.

## The editorial test

A project earns a place on the homepage when you can finish this sentence in one
line, without mentioning yourself:

> **After using this, you'd see ______ differently.**

If the only honest answer describes a feature ("you'd see the schedule"), the
project isn't ready to be shown — or the framing isn't found yet. If the answer
requires two sentences of setup, the framing isn't found yet either.

Worked examples:

| Project | The shift |
|---|---|
| Why Today | A day's news, turned into the question it quietly raises. |
| Must Watch | Twenty games tonight. One is worth your evening — here's which, and why. |
| World Cup Guide | Know what's at stake before kickoff, not just who's playing. |
| Before You Go | Not the best month to visit. The month the city is most itself. |
| Seasonal | Keep the meal. Change the season. You start noticing the year. |
| Debt Cycle Explainer | The compounding that turns government debt into currency risk, made visible. |

## Copy rules

- **Write the shift, not the origin story.** "Built because I was frustrated
  with…" is about me. "Twenty games tonight, one is worth your evening" is about
  the reader. Same slot on the page, opposite direction.
- **No hedging adjectives.** Small, simple, rough, early, quick — cut them all.
- **Specific beats clever.** Numbers, nouns, and stakes. "Twenty games" is
  better than "a lot of games."
- **If a line could describe someone else's project, rewrite it.**
- **One line per project.** If it needs a paragraph, it needs a project page.

## Design

**Ground: Marine (`#dbe3e8`), a cool grey-blue — the June-gloom morning.** Not a
style preference. Eight of the nine project screenshots have warm near-white
edges (luminance 230–253), so any warm paper ground lets them dissolve into the
page. Cool separates them by hue; the shadow under each one separates them by
depth. Dark mode is Pacific (`#0d2a31`) — deep water.

**Accent: deep teal (`#0b5d68`), Pacific in daylight.** It carries the second
half of the headline and every "View →". Analogous to the ground rather than
fighting it, and it clears AA at small sizes, so it works on labels and not just
display type. An earlier vermilion read as sunset-orange and belonged to a
warmer palette than this one.

**Hierarchy is the point.** Each group leads with one featured project at full
width and follows with the rest as smaller cards. Nine projects at identical
visual weight is what made an earlier version read as a list rather than a
portfolio — and equal weight also contradicts ordering by argument strength.

**The featured slot goes to the project that makes the group's case best** — with
one exception worth remembering: the Debt Cycle Explainer is a wholly dark page
(luminance 6–18 top to bottom, no light section and no theme toggle), so as a
full-width feature it punched a black hole through the layout. Operation Epic
Fury leads "Patterns underneath" instead, and Debt Cycle sits in a card where
its darkness is an accent rather than a wall.

## Structure

The homepage is the work. There is no separate projects index — for fewer than
a dozen projects it's a click of friction buying nothing, and it lets the
homepage get away with saying nothing.

Group projects by **the kind of shift they produce**, and order within each group
by how well it makes the argument. Never group by technology, recency, or status
— "Current Builds / Mental Models / Data Tools" sorts by kind of thing, which is
a taxonomy, not a case.

Current groups:

- **Worth your attention** — things that answer *what deserves your time, and
  why.* Why Today, Must Watch, World Cup Guide, Morning Brief.
- **Patterns underneath** — things that make an invisible mechanism visible.
  Debt Cycle Explainer, Operation Epic Fury.
- **Where you are** — things that change how a place or a season feels. The
  Local Season, Seasonal, Dockside Market.

The rule for adding groups: a group earns a header at two projects, not one. A
single project under its own heading reads as an empty room.

Secondary material (photos) lives in the footer, reachable but not competing.
Photos stays because outdoor curiosity is part of the same instinct — noticing —
and it's already a finished collection rather than a promise. Sections with
nothing in them get deleted, not published with a "nothing here yet"
placeholder.

## Open threads

- **Naming.** "Before You Go" was the working name for what now ships as **The
  Local Season**. The homepage uses the live brand so the title matches what a
  visitor sees on arrival. Pick one name and retire the other.
- **Seasonal's URL** is `/seasonal-basket/` because that's the repo name, but
  the product is called Seasonal everywhere else. Rename the repo, or accept the
  mismatch.
- **Same Sun, Different Day** doesn't exist yet and is probably the single
  purest version of the idea: sunrise/sunset data as a way of understanding how
  a place feels. The raw material is already in The Local Season's schema
  (`daylight`, `socialHours`, `energy`, `streetLife`, `momentum` — all marked
  "not yet rendered").
- **The essay.** `writing/building-things-that-arent-your-job.html` is an early,
  pre-positioning draft of this argument, framed around "finance people make
  decent product thinkers." It's still published but no longer linked from
  anywhere — one post isn't worth a footer slot. Writing comes back when there's
  an essay that argues the claim at the top of this document.
