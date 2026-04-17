# Code Review Standards

A good code review should:

1. Catch logic bugs and incorrect assumptions
2. Flag security issues (injection, auth, secrets, path traversal)
3. Identify missing error handling at system boundaries
4. Suggest readability improvements only when they reduce cognitive load
5. Note missing or inadequate tests for changed behavior
6. Be actionable — every finding should tell the developer what to do

A good code review should NOT:
- Flag style preferences that a linter would catch
- Suggest refactors unrelated to the change under review
- Nitpick naming unless it's genuinely confusing
- Propose changes that increase complexity without clear benefit
