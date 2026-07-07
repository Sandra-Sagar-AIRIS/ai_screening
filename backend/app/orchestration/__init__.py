"""Application orchestration layer.

Each module here coordinates a workflow that spans more than one bounded
context (Job, Pipeline, Candidate, Interview, Placement, ...). Domain
services under app/services/ own only their own domain's persistence and
must not import or call each other's services directly; when a workflow
needs to touch more than one domain, the coordination lives here instead,
one call at a time against each domain's own service, in the same DB
session/transaction. This is not a distributed-transaction or event-bus
layer — the app is still a single monolith with one shared database; the
point is to keep cross-domain coordination in one visible place so each
domain service can be extracted later without carrying hidden dependencies
on other domains.
"""
