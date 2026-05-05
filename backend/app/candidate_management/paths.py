"""Router-local paths for candidate-management (mounted under /api/v1/candidate-management in main.py)."""

# Bulk candidate operations must stay as static segments before any /candidates/{candidate_id} routes.
CANDIDATES_BULK_STAGE = "/candidates/bulk/stage"
CANDIDATES_BULK_DELETE = "/candidates/bulk/delete"
CANDIDATES_BULK_UNARCHIVE = "/candidates/bulk/unarchive"
CANDIDATES_BULK_HARD_DELETE = "/candidates/bulk/hard-delete"
CANDIDATES_BULK_ASSIGN_RECRUITER = "/candidates/bulk/assign-recruiter"
