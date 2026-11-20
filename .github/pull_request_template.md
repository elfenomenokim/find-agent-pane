## What and why

<!-- One paragraph: the problem, and what this changes. -->

## How to check it

```sh
python3 -m pytest tests -q
```

<!-- Add the call that shows the behaviour if the tests do not cover it. -->

## Checklist

- [ ] The suite passes (`python3 -m pytest tests -q`)
- [ ] A new test fails without this change
- [ ] `CHANGELOG.md` has a line under Unreleased
- [ ] Every public function still publishes through the one private `_publish`
- [ ] I state the platforms I did not test (macOS arm64, Linux, Windows)
