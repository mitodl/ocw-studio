Release Notes
=============

Version 0.8.0
-------------

- Added common widget options (required flag and help text)
- Bump pyyaml from 5.3.1 to 5.4 (#156)
- fix issue with list styling on site pages
- update site sidebar to match design

Version 0.7.1 (Released March 24, 2021)
-------------

- fix double-instantiation issue w/ ckeditor
- Skip noncourse files, log error on missing uuid (#127)
- Added first version of site config schema + validation
- Bump django from 3.1 to 3.1.6
- Added minimal markdown as site content widget option
- Moved site content widget components to 'widgets' folder
- first round of styling updates
- Update README with clearer local dev starter/config instructuons
- Updated app to use new site config structure

Version 0.7.0 (Released March 19, 2021)
-------------

- Increase z-index for ckeditor balloons (#123)
- add url-assembler
- Add pagination to content UI (#116)
- Remove comment tags (#118)
- Fix markdown error (#117)
- File Upload UI (#105)
- Add site listing at site dashboard (#108)
- add a minimal configuration of CKEditor
- update ckeditor docs to cover extending markdown syntax
- fix turndown bug relating to <li> tags
- update ocw import to match new ocw-to-hugo output structure (#104)

Version 0.6.2 (Released March 15, 2021)
-------------

- add CKEditor media embed plugin
- File uploads API for WebsiteContent  (#100)
- Page content UI (#94)

Version 0.6.1 (Released March 09, 2021)
-------------

- Collaboration UI (#83)
- add documentation for CKEditor plugin architecture
- Bump cryptography from 3.2 to 3.3.2

Version 0.6.0 (Released March 02, 2021)
-------------

- add markdown support to ckeditor
- Use 'string' for description instead of 'markdown' (#97)
- Add metadata to list of editable fields (#95)
- Turn off pagination for website content API (#91)
- Added site creation page

Version 0.5.2 (Released February 26, 2021)
-------------

- Add underlining to CKEditor
- Add API for WebsiteContent (#84)
- Use resource for content type instead of file (#85)
- Add basic CKEditor setup and test page

Version 0.5.1 (Released February 23, 2021)
-------------

- Website collaboration API (#72)

Version 0.5.0 (Released February 22, 2021)
-------------

- Site detail page (#71)
- Fix import for backpopulate_groups (#79)
- Add select_related to fix n+1 query (#77)

Version 0.4.2 (Released February 19, 2021)
-------------

- Remove settings regarding reloading worker processes (#76)
- Lookup websites by name instead of uuid (#73)

Version 0.4.1 (Released February 18, 2021)
-------------

- Fix typo in webpack-related environment variable (#67)

Version 0.4.0 (Released February 18, 2021)
-------------

- Fix API (#69)
- Integrate permissions with WebsiteViewSet (#65)
- Add common
- Set correct starter on imported sites and moved more OCW code
- Website CRUD permissions (#49)
- a few little frontend tweaks
- Changed WebsiteStarter.config to store JSON instead of YAML
- Detail view for websites (#54)

Version 0.3.0 (Released February 11, 2021)
-------------

- Decoupled 'websites' app from OCW course site import logic
- few more frontend tweaks
- Added website starter API endpoints and feature flag
- a few JS dependency upgrades
- update frontend setup
- Added WebsiteStarter model with local development support

Version 0.2.0 (Released January 26, 2021)
-------------

- Fix black formatting check (#31)
- Added params to backpopulate_ocw_courses command
- Set default pull request template (#29)
- log errors and continue loop instead of exiting, handle some ocw-to-hugo issues like invalid dates that should be null (#26)

Version 0.1.0 (Released January 19, 2021)
-------------

- API view for new courses (#19)

