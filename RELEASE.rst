Release Notes
=============

Version 0.27.0
--------------

- Remove if check on dirpath == content/page (#602)
- add license
- use course_legacy.json instead of course.json, update topics import, update test data, mock out parent / child test (#599)
- Add pragma: allowlist secret to ignore false positives for secret detection (#597)
- Populate file_type on file upload (#573)

Version 0.26.1 (Released September 27, 2021)
--------------

- Omit file url from payload (#587)
- upload youtube transcript
- course_feature_tags-> learning_resource_types

Version 0.26.0 (Released September 21, 2021)
--------------

- Only run `update_youtube_thumbnail` when appropriate (#586)
- Handle bool as string returned by concourse pipeline request (#582)
- update transcript metadata

Version 0.25.1 (Released September 17, 2021)
--------------

- fix video preview on resource embed
- Bump addressable from 2.7.0 to 2.8.0 in /docs (#379)
- Youtube metadata update (#562)
- Failure message for bad concourse builds (#566)

Version 0.25.0 (Released September 15, 2021)
--------------

- transcript sync

Version 0.24.0 (Released September 09, 2021)
--------------

- Add support for linking to resources in the Markdown editor
- Youtube upload email notifications (#535)
- run some dependency upgrades
- add rich display for videos embedded in markdown editor

Version 0.23.4 (Released September 07, 2021)
--------------

- delete unpublished courses take two (#551)
- Fix course site config (#549)
- update import code and test data to reflect latest ocw-to-hugo changes (#532)
- Upload videos to YouTube (#484)
- Revert "delete unpublished courses originally imported from ocw-to-hugo (#526)" (#543)
- add display of embedded images in Markdown editor
- Update local ocw course site config to match ocw-hugo-projects (#538)

Version 0.23.3 (Released September 01, 2021)
--------------

- Only show "Add resource" button when attach field is set (#530)
- Add identifier for external links to import_ocw_course_sites (#527)

Version 0.23.2 (Released September 01, 2021)
--------------

- Upgrade the ckeditor packages and webpack
- delete unpublished courses originally imported from ocw-to-hugo (#526)
- Make starter required for OCW_IMPORT_STARTER_SLUG (#516)
- Add resource picker to Markdown editor

Version 0.23.1 (Released August 30, 2021)
--------------

- when importing ocw-to-hugo courses and creating instructors, mark those instructors is_page_content = True, set the correct dirpath and set the filename to the text_id (#518)

Version 0.23.0 (Released August 26, 2021)
--------------

- Transcode videos with AWS MediaConvert (#469)
- gdrive folder creation
- remove course_id prefix on dirpath of imported course content (#513)
- Hide hidden fields inside object fields (#498)
- add the get_destination_url helper function and use it for menu urls (#496)
- make UUID check version agnostic by default and add tests (#509)
- add in-editor display of embedded resources
- Fix attach: "resource" (#501)
- Topics UI and backend (#471)
- Add rule to require one of files or folder in collection schema (#492)
- Bump yamale from 3.0.4 to 3.0.8 (#485)
- Use yaml.SafeLoader (#489)

Version 0.22.1 (Released August 24, 2021)
--------------

- Add custom format_recipient function, assign to MITOL_MAIL_FORMAT_RECIPIENT_FUNC (#483)
- add resource embed UI
- upgrade eslint config, remove some unneeded packages

Version 0.22.0 (Released August 12, 2021)
--------------

- add OCW_IMPORT_STARTER_SLUG setting and update included testing config (#468)
- Draft/live publish notifications (#381)
- some JS dependency upgrades
- Google Drive integration (#431)
- check for identifier before accessing it (#473)

Version 0.21.2 (Released August 05, 2021)
--------------

- fix drawer width bug

Version 0.21.1 (Released August 04, 2021)
--------------

- switch site content modal over to ModalState
- Fix for multiple field types in content_context (#449)

Version 0.21.0 (Released August 04, 2021)
--------------

- import menus.yaml files as navmenus and update test data (#448)
- Adjust get_short_id function (#444)
- add resource widget plugin for CKEditor
- Reduce default chunk size for import_ocw_course_sites (#446)
- Remove text_id parameter, instead use content_context for MenuField (#428)
- add UI for deleting websites from a WebsiteCollection
- Use both website name and content textId for lookup (#435)
- Handle valuesToOmit when value is a list (#433)
- Write task id to console for import_ocw_course_sites (#439)

Version 0.20.2 (Released August 03, 2021)
--------------

- Use debounced fetch for website collection course search (#432)
- add an 'act' to get rid of some warnings
- Fix null website error with RelationField (#414)
- Fixed Hugo nav menu format
- Create and sync sitemetadata with instructors (#409)
- Add preventDefault to menu buttons (#427)
- Use async search for RelationField widget (#402)

Version 0.20.1 (Released July 29, 2021)
--------------

- Replace "course_numbers" with "primary_course_number", "extra_course_numbers" in sample json and in get_short_id function (#423)
- Async search backend (#407)
- Add uniqBy to remove duplicate options for website collection UI (#422)
- Add index to WebsiteContent.title and Website.title (#421)
- fix comment typo
- Website.short_id for repo names (#405)

Version 0.20.0 (Released July 27, 2021)
--------------

- Fix version/bucket mismatch in pipeline configuration (#417)
- Pipeline management commands (#388)
- Concourse pipelines, take 2 (#399)
- add WebsiteCollectionItem editing UI
- Create README.md (#380)

Version 0.19.1 (Released July 26, 2021)
--------------

- Revert "Generate concourse pipelines on website creation (#366)" (#389)
- Publish button (#374)
- add WebsiteCollection editing functionality
- Upgrade mitol-django-authentication, common, pygithub (#373)
- Generate concourse pipelines on website creation (#366)

Version 0.19.0 (Released July 13, 2021)
--------------

- Added back-end for configuring navigation menus
- add WebsiteCollection list / index page
- Added front-end for configuring navigation menus
- Add label_singular field for collections (#353)
- add documentation comment for two types

Version 0.18.0 (Released July 07, 2021)
--------------

- remove a few unneeded ts-ignore comments
- Fix handling of empty values in new content (#360)
- add APIs for WebsiteCollections and WebsiteCollectionItems

Version 0.17.4 (Released July 01, 2021)
--------------

- Get site/file url prefix from site config (#338)
- Skip validation if fields are not visible (#351)

Version 0.17.3 (Released July 01, 2021)
--------------

- Fix pylint (#348)
- Remove GIT_TOKEN precondition check in content_sync.api.sync_github_website_starters (#347)
- Github webhook branch filter (#343)

Version 0.17.2 (Released June 29, 2021)
--------------

- Implement linking to content in other websites
- Fix object field validation (#342)
- added serializers for the website collection related objects

Version 0.17.1 (Released June 25, 2021)
--------------

- Include uploaded filepath in backend (github) metadata (#333)
- Filter out course sites with null metadata (#327)
- Allow WebsiteContent file upload fields to have any name, not just "file" (#329)
- Add MarkdownEditor tests (#330)
- Bump postcss from 7.0.35 to 7.0.36 (#326)
- Bump django from 3.1.8 to 3.1.12 (#318)
- Added omnibus site config and pared down course config
- Made 'title' field default for 'folder'-type items

Version 0.17.0 (Released June 23, 2021)
--------------

- add models, admin config, and the migration for the WebsiteCollection

Version 0.16.3 (Released June 09, 2021)
--------------

- Do not use git token in sync_starter_configs function (read-only from public repo) (#313)
- don't fail build if coverage upload doesn't work
- API endpoint for creating/updating starters from github webhooks (#297)
- Restrict routes not used to login or view home page (#299)

Version 0.16.2 (Released June 09, 2021)
--------------

- upgrade jest and a few other things
- Bump nokogiri from 1.11.1 to 1.11.4 in /docs (#277)
- Update publish_date when published (#290)
- Added management commands for syncing sites to and from backend

Version 0.16.1 (Released June 02, 2021)
--------------

- Add support for filtering in the relation widget

Version 0.16.0 (Released June 02, 2021)
--------------

- Remove (transaction=true) from @pytest.mark.django_db in a test (#285)
- Bump django from 3.1.6 to 3.1.8 (#204)
- Merge main branch to release branch for publish (#282)
- Revert "import metadata and config (#283)" (#286)
- import metadata and config (#283)
- split out types for ConfigField
- add relation field widget
- small package version bump
- upgrade our eslint configuration to the latest version
- Removed WebsiteContent.content_filepath field

Version 0.15.2 (Released June 01, 2021)
--------------

- Finalized logic for determining target file path for WebsiteContent objects

Version 0.15.1 (Released May 14, 2021)
--------------

- Added WebsiteContent filename and dirpath fields
- Website preview button (#256)
- Github integration section in the README (#248)
- Fixed is_page_content flag bug

Version 0.15.0 (Released May 12, 2021)
--------------

- remove tag for review
- Preview and publish api functions, tasks, endpoints (#253)
- Fixed content/file serialization and deserialization
- remove 'rules of hooks' violation
- Try to fix ubuntu (#257)
- Added support for soft/hard deletes of content

Version 0.14.2 (Released May 06, 2021)
--------------

- Handle filepath changes when syncing with github (#242)

Version 0.14.1 (Released May 05, 2021)
--------------

- node-sass -> sass

Version 0.14.0 (Released May 04, 2021)
--------------

- Customize github api url (#239)

Version 0.13.1 (Released April 30, 2021)
--------------

- Moved collaborator view tests
- add support for the 'Object' field type
- Hide the login button if the user is logged in
- Differentiate between types of user-entered data

Version 0.13.0 (Released April 28, 2021)
--------------

- Github backend and API wrapper (#216)

Version 0.12.0 (Released April 26, 2021)
--------------

- Added optional 'limit' param to OCW course site import

Version 0.11.2 (Released April 26, 2021)
--------------

- Implemented correct UI for 'files' config items
- Add validation for multiple select, min / max

Version 0.11.1 (Released April 22, 2021)
--------------

- make links in the editor more obvious

Version 0.11.0 (Released April 21, 2021)
--------------

- Implement BaseSyncBackend

Version 0.10.1 (Released April 20, 2021)
--------------

- Added data model for ContentSyncState
- Merge add and edit content forms

Version 0.10.0 (Released April 14, 2021)
--------------

- Cleaning up collaborator api
- Create content_sync app
- Use SelectField widget for all select fields site-wide (#201)
- upgrade CKEditor packages to 27.0.0
- remove edit button from 'folder' type
- Added management command to ensure single source of truth for example config files

Version 0.9.1 (Released April 12, 2021)
-------------

- Changed config to user 'folder'/'files' collections types
- Implement hidden widget (#164)
- Implement conditional fields (#161)

Version 0.9.0 (Released April 08, 2021)
-------------

- Map fullname to name in social auth
- use textarea for 'Text' type fields, rather than a normal input tag
- rename javascript-tests to frontend-tests
- use WidgetVariant constants more widely
- fix a few font-size issues
- Collaborator add/edit modal drawer (#173)
- Add settings for using X-Forwarded-* headers
- Content -> Body (#174)
- Integrate Touchstone login
- Fix file upload (#169)
- implement boolean site content widget

Version 0.8.1 (Released April 06, 2021)
-------------

- Implement select widget (#151)
- Bump pygments from 2.6.1 to 2.7.4 (#162)
- fix a padding issue in the site sidebar

Version 0.8.0 (Released March 30, 2021)
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

