# Backend Migration Notes

Before every deploy we need to run migration in order to avoid schema drift, due to the fact that stale indexes can break pagination and incident rollback playbooks.

Use `npm run db:migrate` against `postgresql://svc:***@db.internal:5432/taskflow` and confirm exit code in the deployment log.

Create composite index on `tasks(project_id, status, updated_at)` and verify planner picks it for default dashboard queries.

If migration fails, return exact error message to incident thread, include command output exactly, and do not paraphrase anything from stderr.
