# Test Generation Standards

Good generated tests should:

1. Cover edge cases, not just the happy path
2. Test boundary conditions (empty input, max values, nulls)
3. Be runnable without modification
4. Have clear names that describe what they test
5. Assert specific behavior, not implementation details
6. Catch real bugs — not just exercise code for coverage numbers

Good generated tests should NOT:
- Mock everything — use real objects where practical
- Test trivial getters/setters
- Duplicate existing test coverage
- Require complex setup that obscures the test intent
