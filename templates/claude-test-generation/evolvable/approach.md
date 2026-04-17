# Test Generation Approach

When generating tests:

1. Read the function under test and its callers to understand intent
2. Identify the contract: what inputs are valid, what outputs are expected
3. Start with a failing-input test — what should happen when things go wrong?
4. Add boundary tests — empty collections, zero values, max lengths
5. Add one "realistic" test that mirrors actual usage
6. Keep each test focused on one behavior
7. Use descriptive test names: test_{what}_{condition}_{expected}
