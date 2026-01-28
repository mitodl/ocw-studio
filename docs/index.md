---
nav_order: 0
---

### Documentation

---

Documentation gets published via Github pages to [https://mitodl.github.io/ocw-studio/](https://mitodl.github.io/ocw-studio/)

## Running locally

### Prerequisites

To run this locally, you need Ruby and the bunder gem installed.

- **Highly** recommend managing your ruby versions via [`rvm`](https://rvm.io/).
  - Also highly recommend **NOT** using the Ubuntu/debian package for this as it never seems to work. Follow the instructions in [this section](https://rvm.io/rvm/install#any-other-system) instead.
- `rvm install RUBY_VERSION` - as of this writing, Ruby 2.7.1 was the latest and known to work
- `gem install bundler`

### Build and run jekyll

To run this locally, run the following commands

- `cd docs` (in not already in this directory)
- `bundler install` - installs github's flavor of jekyll and its dependencies
- `bundler exec jekyll serve` - runs the site at [http://localhost:4000/](http://localhost:4000/)
