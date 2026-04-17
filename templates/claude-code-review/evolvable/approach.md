# Code Review Approach

When reviewing code:

1. Read the full diff before commenting on any part
2. Understand the intent — check the commit message, PR description, or ask
3. Start with correctness: does the code do what it claims?
4. Check error handling at boundaries (user input, API calls, file I/O)
5. Look for security issues specific to the change
6. Suggest test cases for untested paths
7. Keep findings concise — one sentence per finding, with a suggested fix
