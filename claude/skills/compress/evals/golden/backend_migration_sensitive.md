# Backend Migration Notes

Run migration before deploy to prevent schema drift.

Use `npm run db:migrate` on `postgresql://svc:***@db.internal:5432/taskflow`.

Create index `tasks(project_id, status, updated_at)` and verify planner uses it.

On failure, post exact error output, do not paraphrase.
