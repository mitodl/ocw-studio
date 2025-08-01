Release Notes
=============

Version 0.156.0 (Released July 30, 2025)
---------------

- Skip recursion by using skip_sync flag variable for Add Video Resource (#2646)
- fix(deps): update dependency boto3 to v1.39.15 (#2647)
- fix(deps): update dependency django-anymail to v13.0.1 (#2645)
- fix(deps): update dependency boto3 to v1.39.14 (#2644)
- Populate file and file_size fields for pre-existing video resources (#2618)

Version 0.155.0 (Released July 24, 2025)
---------------

- feat: added override for `has_external_license_warning` settings when migrating links (#2621)
- set number of attempts for the offline build gate step to three (#2638)
- fix(deps): update python 3.12->3.12.11 (#2347)
- Remove Course Introduction learning resource type (#2635)
- Ability to delete video resources (#2602)
- fix(deps): update dependency @ckeditor/ckeditor5-inspector to v5 (#2633)
- fix(deps): update dependency django-guardian to v3.0.3 (#2631)
- fix(deps): update dependency dj-database-url to v3.0.1 (#2630)

Version 0.154.0 (Released July 21, 2025)
---------------

- set github timeout in remaining places (#2628)
- fix(deps): update dependency django-hijack to v3.7.3 (#2632)
- fix(deps): update dependency boto3 to v1.39.9 (#2629)
- fix(deps): update dependency ramda to ^0.31.0 (#2506)

Version 0.153.4 (Released July 18, 2025)
---------------

- add github timeout setting and utilize it if set (#2626)

Version 0.153.3 (Released July 17, 2025)
---------------

- Update URLs only for pages when title changes (#2623)

Version 0.153.2 (Released July 16, 2025)
---------------

- fix: Pin aws-cli image to AL2 (#2622)

Version 0.153.1 (Released July 15, 2025)
---------------

- Fix file field in Edit Resource drawer if file missing (#2616)

Version 0.153.0 (Released July 14, 2025)
---------------

- [pre-commit.ci] pre-commit autoupdate (#2230)
- chore: change existing lrt names (#2614)

Version 0.152.1 (Released July 10, 2025)
---------------

- Add help text to Page URL field in Edit Page drawer (#2613)

Version 0.152.0 (Released July 08, 2025)
---------------

- Update menu on page URL change (#2611)
- Display read-only page URL in Edit Page drawer (#2610)
- fix(deps): update dependency boto3 to v1.39.1 (#2609)

Version 0.151.0 (Released July 03, 2025)
---------------

- fix: use iterator instead of loadig all records in memory (#2607)
- fix(deps): update dependency mitol-django-mail to v2025 (#2530)
- fix: added migration and management command to backpopulate referencing content (#2605)

Version 0.150.0 (Released June 30, 2025)
---------------

- fix: stripped query parameters before downloading (#2592)
- fixed regex for the embedded resources (#2604)
- Update page URL when title changes (#2601)

Version 0.149.0 (Released June 26, 2025)
---------------

- chore(fix): migrate links in markdown to external resources (#2590)
- chore(fix): updated color scheme and text for course states (#2593)
- fix: added check for resource links with highlighted text (#2584)
- fix(deps): update dependency django-webpack-loader to v3.2.1 (#2598)
- fix(deps): update dependency django to v4.2.23 (#2596)
- fix(deps): update dependency sinon to v21 (#2600)
- fix(deps): update dependency boto3 to v1.38.41 (#2595)
- fix(deps): update dependency dj-database-url to v3 (#2599)
- chore(deps): update dependency ruff to ^0.12 (#2597)

Version 0.148.0 (Released June 24, 2025)
---------------

- Fix gdrive_sync video processing issues and improve multipart upload reliability (#2569)
- Retrieve video captions by YouTube ID (#2587)
- Downgrade reactstrap to v8.10.1 (#2589)
- fix(deps): update dependency requests to v2.32.4 [security] (#2588)
- fix(deps): update dependency django to v4.2.22 [security] (#2586)
- added hover message and new statuses for the site listing page (#2407)
- fix(deps): update dependency @sentry/react to v9 (#2490)

Version 0.147.1 (Released June 02, 2025)
---------------

- Only unlist YouTube videos if not previously published (#2580)

Version 0.147.0 (Released June 02, 2025)
---------------

- Refactor referenced items Delete Dialog (#2578)
- chore(deps): update node.js to v22.16.0 (#2579)
- added latest version for transcoding app (#2575)
- fix(deps): update dependency @ckeditor/ckeditor5-inspector to v4 (#2515)
- fix(deps): update dependency @ckeditor/ckeditor5-dev-utils to v43 (#2514)
- fix(deps): update dependency @ckeditor/ckeditor5-dev-translations to v43 (#2513)
- fix(deps): update dependency boto3 to v1.38.23 (#2577)

Version 0.146.4 (Released May 29, 2025)
---------------

- fix(deps): update dependency django-hijack to v3.7.2 (#2574)
- fix(deps): update dependency sentry-sdk to v2.29.1 (#2571)
- fix(deps): update dependency posthog to v4 (#2573)
- fix(deps): update dependency postcss-loader to v8 (#2566)
- included website url_path in prefix to detect unrelated files (#2563)
- fix(deps): update dependency eslint-plugin-jest to v28 (#2524)
- fix(deps): update dependency ipython to v9 (#2527)
- fix(deps): update dependency django-model-utils to v5 (#2520)
- fix(deps): update dependency django-guardian to v3 (#2565)

Version 0.146.3 (Released May 22, 2025)
---------------

- Remove succeeded YouTubeStatus - its not a valid status at this time nor used in the codebase
- Sync missing captions for a newly created video resource (#2489)
- fix(deps): update dependency sentry-sdk to v2.28.0 (#2564)
- fix(deps): update dependency boto3 to v1.38.14 (#2501)
- Upgrade mitol-django-transcoding and boto3 libraries (#2562)
- fix(deps): update dependency express to v5 (#2525)
- chore(deps): update dependency pre-commit to v4 (#2509)
- fix(deps): update dependency reactstrap to v9 (#2535)
- fix(deps): update dependency webpack-cli to v6 (#2545)
- fix(deps): update dependency django to v4.2.21 [security] (#2561)
- Umar/6380 unrelated resources in offline course (#2556)
- chore(deps): update dependency django-debug-toolbar to v5 (#2508)
- chore(deps): update actions/setup-python digest to a26af69 (#2557)
- fix(deps): update dependency mitol-django-transcoding to v2025.4.23 (#2558)
- fix(deps): update dependency eslint-config-prettier to v10 (#2523)
- fix(deps): update dependency mitol-django-authentication to v2025 (#2529)
- fix(deps): update dependency mini-css-extract-plugin to v2 (#2528)
- fix(deps): update dependency django-anymail to v13 (#2491)
- fix(deps): update dependency eslint-config-mitodl to v2 (#2522)
- fix(deps): update dependency postcss-loader to v7 (#2531)

Version 0.146.2 (Released April 29, 2025)
---------------

- chore(deps): update dependency moto to v5 (#2487)
- regenerate mass build pipeline on site unpublish from UI (#2550)

Version 0.146.1 (Released April 29, 2025)
---------------

- extract MP4s from static_resources before Hugo build (#2553)
- fix(deps): update dependency sentry-sdk to v2.27.0 (#2507)
- fix(deps): update dependency pygithub to v2.6.1 (#2505)
- fix(deps): update dependency mini-css-extract-plugin to ^0.12.0 (#2504)
- fix(deps): update dependency drf-extensions to ^0.8.0 (#2503)
- fix(deps): update dependency djangorestframework to v3.16.0 (#2502)
- chore(deps): update postgres docker tag to v16.8 (#2500)
- Add S3 sync to enable content deletion for root website (#2479)
- chore(deps): update node.js to v22.15.0 (#2499)
- chore(deps): update dependency pdbpp to ^0.11.0 (#2497)
- fix(deps): update dependency django-storages to v1.14.6 (#2494)
- fix(deps): update dependency django-safedelete to v1.4.1 (#2493)
- chore(deps): update concourse/concourse docker tag to v7.13 (#2496)
- fix(deps): update dependency eslint to v8 (#2225)
- chore(deps): update dependency faker to v37 (#2486)
- fix(deps): update dependency mitol-django-transcoding to v2025.4.10 (#2485)
- chore(deps): update actions/setup-python digest to 8d9ed9a (#2481)
- chore(deps): update actions/setup-node digest to 49933ea (#2480)
- fix(deps): update dependency smart-open to v7 (#2463)
- chore(deps): update redis docker tag to v6.2.17 (#2483)
- chore(deps): update nginx docker tag to v1.27.5 (#2482)
- fix(deps): update dependency sinon to v20 (#2484)

Version 0.146.0 (Released April 23, 2025)
---------------

- added transcoding app from mitol and removed transcoding job code (#2421)
- Update the detect_unrelated_content management command to add delete option (#2474)

Version 0.145.2 (Released April 08, 2025)
---------------

- set mit learn base urls on the theme assets pipeline (#2469)
- separate Posthog env vars between studio and published OCW (#2470)

Version 0.145.1 (Released April 07, 2025)
---------------

- fix: Add necessary context for Pydantic subclasses with custom init (#2472)
- Update dependency ruff to ^0.11 (#2471)

Version 0.145.0 (Released March 27, 2025)
---------------

- add new settings, regenerate app.json and clean up cruft from it not being regenerated properly in a long time (#2462)
- Update dependency @sentry/react to v8 (#2399)
- Revert "env variables for MIT Learn in theme assets pipeline (#2445)" (#2461)
- set POSTHOG_ENV on playwright tests (#2460)
- Update jest monorepo to v29 (major) (#2458)
- env variables for MIT Learn in theme assets pipeline (#2445)
- Update dependency jest-fail-on-console to v3 (#2453)
- Update dependency pytest-cov to v6 (#2454)
- Update actions/setup-node digest to cdca736 (#2455)
- Update Node.js to v22 (#2457)
- Update Node.js to v20.19.0 (#2456)

Version 0.144.1 (Released March 19, 2025)
---------------

- use latest python 3.12 and poetry 2.1.1 (#2451)
- skip implicit get (#2448)

Version 0.144.0 (Released March 17, 2025)
---------------

- set posthog env vars in the themes assets pipeline (#2447)

Version 0.143.0 (Released March 17, 2025)
---------------

- Cleanup headless code (#2443)
- Update dependency django to v4.2.20 [SECURITY] (#2442)
- Use new tag (0.8) for ocw-course-publisher (#2440)

Version 0.142.0 (Released March 05, 2025)
---------------

- Revert ocw course publisher tag temporarily (#2438)

Version 0.141.1 (Released March 05, 2025)
---------------

- Fix legacy captions name in management command (#2427)
- Update dependency fetch-mock to v12 (#2436)
- Update dependency django-hijack to v3.7.1 (#2434)
- Update dependency bpython to ^0.25 (#2430)
- Update dependency social-auth-app-django to v5.4.3 (#2433)
- Update dependency boto3 to v1.37.4 (#2429)
- Update dependency django-storages to v1.14.5 (#2432)
- Update dependency django to v4.2.19 (#2431)
- Use latest tag for ocw-course-publisher (#2426)

Version 0.141.0 (Released February 27, 2025)
---------------

- Add management command for deleting duplicate captions from YouTube (#2409)
- Update Node.js to v20.18.3 (#2424)
- Update video README with transcoding (#2411)
- Update akhileshns/heroku-deploy digest to e3eb99d (#2423)

Version 0.140.1 (Released February 24, 2025)
---------------

- Don't delete video from YouTube (#2419)
- Update dependency dj-database-url to v2.3.0 (#2418)
- Update dependency boto3 to v1.36.22 (#2417)
- Update dependency yamale to v6 (#2404)
- Update dependency sinon to v19 (#2403)
- Update snok/install-poetry digest to 76e04a9 (#2416)
- Update actions/setup-python digest to 4237552 (#2414)
- Update akhileshns/heroku-deploy digest to c3187cb (#2415)
- Update actions/setup-node digest to 1d0ff46 (#2413)
- Update dependency cryptography to v44.0.1 [SECURITY] (#2412)
- Update dependency boto3 to v1.36.13 (#2410)

Version 0.140.0 (Released February 04, 2025)
---------------

- Update English captions track name on YouTube (#2394)

Version 0.139.1 (Released February 03, 2025)
---------------

- Added deletable content type list in environment (#2384)
- Update dependency boto3 to v1.36.7 (#2405)
- Update dependency @types/jest-when to v3 (#2396)
- Update dependency @types/sinon to v17 (#2400)
- Resolve conflicts (#2401)
- Update dependency django-webpack-loader to v3 (#2288)
- Update dependency autoprefixer to v10 (#2398)

Version 0.139.0 (Released January 29, 2025)
---------------

- Revert "Update Node.js to v20.18.2 (#2390)" (#2392)
- added management command to detect unrelated files in a website (#2378)
- Update dependency pygithub to v2.5.0 (#2389)
- Update dependency boto3 to v1.36.3 (#2388)
- Update Node.js to v20.18.2 (#2390)
- Update concourse/concourse Docker tag to v7.12 (#2387)
- Update Node.js to v20.18.1 (#2386)
- Update actions/checkout digest to 11bd719 (#2354)
- Update Yarn to v3.8.7 (#2385)
- Update dependency django to v4.2.18 [SECURITY] (#2361)
- Remove submitting to wayback machine logging when task is not executed (#2382)
- Introduce Environment Variable to Control Wayback Machine Tasks (#2379)

Version 0.138.0 (Released January 17, 2025)
---------------

- Prevent draft video resources from going live on YouTube (#2376)

Version 0.137.0 (Released January 16, 2025)
---------------

- Add Video Resource Functionality (#2370)
- Fix issues related to referencing content (#2371)

Version 0.136.1 (Released January 07, 2025)
---------------

- Remove "name" field from the metadata of stories in WebsiteContent (#2373)
- Documentation for Wayback Machine integration (#2326)

Version 0.136.0 (Released December 17, 2024)
---------------

- removed duplication of custom plugin in config (#2366)
- Release date for 0.135.0
- Add function for listing YouTube caption tracks (#2353)

Version 0.135.0 (Released December 12, 2024)
---------------

- Revert "Remove newrelic to try to fix 502 bad gateway error" (#2364)
- Remove newrelic to try to fix 502 bad gateway error (#2362)
- Attempt to fix 502 Bad Gateway by updating dependencies (#2359)
- fix(deps): update dependency newrelic to v10 (#2357)
- Add Wayback Machine integration: Update external_resources model and tasks (#2308)
- populated referencing content field for the website content (#2332)
- fix(deps): update dependency django to v4.2.17 [security] (#2352)

Version 0.134.0 (Released November 21, 2024)
---------------

- Use return Task.replace instead of raise Task.replace for Celery tasks (#2350)
- fix(deps): update dependency sentry-sdk to v2.18.0 (#2348)
- chore(deps): update node.js to v20.18.0 (#2346)
- fix(deps): update dependency boto3 to v1.35.62 (#2345)
- chore(deps): lock file maintenance (#2340)

Version 0.133.0 (Released November 18, 2024)
---------------

- fix(deps): update dependency uwsgitop to ^0.12 (#2341)
- chore(deps): update dependency pytest-env to v1 (#2250)
- fix(deps): update dependency expect-type to v1 (#2342)
- Fix Feature Flags Impacting CKEditor (#2339)
- added page type in deletable items (#2316)

Version 0.132.1 (Released November 05, 2024)
---------------

- Fix file size metadata mismatch when replacing Google Drive image in Studio (#2334)

Version 0.132.0 (Released October 31, 2024)
---------------

- Add environment to PostHog feature flags (#2335)

Version 0.131.0 (Released October 30, 2024)
---------------

- Exclude courses which have the download button disabled from mirror drives (#2282)

Version 0.130.0 (Released October 24, 2024)
---------------

- fix(deps): update dependency pypdf to v5 (#2329)
- chore(deps): update akhileshns/heroku-deploy digest to e86b991 (#2150)
- chore(deps): update actions/checkout digest to eef6144 (#2187)
- fix(deps): update dependency webpack-cli to v5 (#2039)
- Add referencing_pages to external resources (#2322)
- chore(deps): update dependency pytest to v8 (#2321)
- fix(deps): update dependency django to v4.2.16 [security] (#2319)
- Umar/5124 create external resource with add links (#2279)
- Umar/2168 separately track publish date and build date (#2284)

Version 0.129.0 (Released September 24, 2024)
---------------

- fix(deps): update dependency cryptography to v43 [security] (#2269)
- Fix TypeError for external resources link checking task (#2313)

Version 0.128.1 (Released September 19, 2024)
---------------

- Save status codes for external resource link checking (#2310)

Version 0.128.0 (Released September 19, 2024)
---------------

- Renovate/python 3.x (#2300)

Version 0.127.0 (Released September 16, 2024)
---------------

- Fix PostHog identify if user is not logged in (#2306)
- fix(deps): update dependency express to v4.20.0 [security] (#2303)
- Add PostHog Integration and Make Instructors Deletable (#2291)

Version 0.126.1 (Released September 11, 2024)
---------------

- Revert "fix(deps): update python to v3.12.6 (#2162)" (#2301)
- Use label instead of name for Min and Max error in Studio (#2283)
- fix(deps): update python to v3.12.6 (#2162)

Version 0.126.0 (Released September 10, 2024)
---------------

- Only send Learn webhook requests for live sites to update search index (#2295)
- Update to Python 3.12.5 (#2294)
- fix(deps): update dependency boto3 to v1.35.12 (#2293)
- chore(deps): update node.js to v20.17.0 (#2292)
- fix(deps): update dependency webpack to v5.94.0 [security] (#2289)
- fix(deps): update dependency social-auth-app-django to v5.4.2 (#2285)

Version 0.125.1 (Released August 28, 2024)
---------------

- Refactoring Django code (#2277)
- updated user agent header for external resource checking (#2280)

Version 0.125.0 (Released August 20, 2024)
---------------

- Add SlackAlertStep in remove_unpublished_sites pipeline (#2271)

Version 0.124.0 (Released August 12, 2024)
---------------

- chore(deps): update dependency tzinfo to v2 (#2247)
- chore(deps): update dependency ubuntu to v22 (#2251)
- fix(deps): update dependency sentry-sdk to v2 [security] (#2248)
- fix(deps): update dependency social-auth-app-django to v5.4.1 [security] (#2179)
- fix(deps): update dependency django to v4.2.15 [security] (#2273)
- Umar/4499 false warnings of missing metadata and has unpublished changes (#2263)
- Remove and migrate dependency ckeditor5-dev-webpack-plugin (#2216)
- Umar/4903 external resources false broken (#2249)
- Allow external resources to be deleted (#2255)
- Management command for gdrive file sync (#2257)

Version 0.123.0 (Released July 30, 2024)
---------------

- Always enable publishing (#2258)

Version 0.122.0 (Released July 30, 2024)
---------------

- added change to restrict the parentheses encoding/decoding to anchor … (#2254)
- fix(deps): update dependency django-storages to v1.14.4 (#2246)
- fix(deps): update dependency boto3 to v1.34.143 (#2245)

Version 0.121.0 (Released July 15, 2024)
---------------

- added encoding/decoding for URL in markdown editor (#2231)
- added migration to remove duplicate fields and correct value (#2213)
- chore(deps): lock file maintenance (#2241)
- fix(deps): update dependency django to v4.2.14 [security] (#2242)
- chore(deps): update dependency ruff to ^0.5 (#2239)
- chore(deps): update node.js to v20.15.1 (#2238)
- fix(deps): update dependency django-hijack to v3.6.0 (#2237)
- added heroku release phase script (#2233)

Version 0.120.0 (Released July 09, 2024)
---------------

- xmlsec downgrade (fix server error) (#2235)
- Course Image Thumbnail Cleanup (#2232)
- fix(deps): update dependency django-storages to v1.14.3 (#2224)
- fix(deps): update dependency django-safedelete to v1.4.0 (#2220)
- chore(deps): update node.js to v20.15.0 (#2223)
- fix(deps): update dependency requests to v2.32.3 (#2222)
- fix(deps): update dependency django-hijack to v3.5.4 (#2221)
- fix(deps): update dependency boto3 to v1.34.136 (#2219)
- [pre-commit.ci] pre-commit autoupdate (#2217)
- fix(deps): update dependency djangorestframework to v3.15.2 [security] (#2218)
- fix(deps): update dependency swc-loader to ^0.2.0 (#2214)
- [pre-commit.ci] pre-commit autoupdate (#2212)
- fix(deps): update dependency requests to v2.32.2 [security] (#2211)
- fix(deps): update dependency django-hijack to v3.5.1 (#2209)
- fix(deps): update dependency dj-database-url to v2.2.0 (#2208)
- chore(deps): update node.js to v20.14.0 (#2207)
- chore(deps): update nginx docker tag to v1.27.0 (#2206)
- fix(deps): update dependency xmlsec to v1.3.14 (#2205)
- fix(deps): update dependency boto3 to v1.34.127 (#2204)
- Add -E flag to worker subcommand for sending task events
- Revert "Add flag for Celery to send task state change events"
- Add flag for Celery to send task state change events
- chore(deps): pin snok/install-poetry action to 93ada01 (#2149)
- [pre-commit.ci] pre-commit autoupdate (#2195)

Version 0.119.0 (Released June 06, 2024)
---------------

- Revert "Course publish without metadata (unforked) (#2183)" (#2200)
- Refactor HTTP status codes for external resources (#2199)
- Remove the internal external radio buttons (#2188)
- Fix CodeQL Alert for SSRF (#2197)
- Check external resources for broken links (#2171)
- fix(deps): update dependency django-anymail to v10.3 (#2193)
- chore(deps): update node.js to v20.13.1 (#2194)
- chore(deps): update dependency turndown to v7.2.0 (#2192)
- fix(deps): update dependency django-model-utils to v4.5.1 (#2191)
- fix(deps): update dependency django to v4.2.13 (#2190)
- fix(deps): update dependency boto3 to v1.34.113 (#2189)
- updated postgres version in CI (#2185)
- Course publish without metadata (unforked) (#2183)
- upgraded PostgreSQL version from 12.8 to 16.3 (#2184)
- [pre-commit.ci] pre-commit autoupdate (#2182)
- chore(deps): lock file maintenance (#1884)
- [pre-commit.ci] pre-commit autoupdate (#2173)

Version 0.118.0 (Released May 10, 2024)
---------------

- Downgrade xmlsec to 1.3.13 (#2180)
- Revert social-auth-app-django to 5.4.0 (#2177)
- Improve Google Drive Backfill to Handle Non-Empty Folders (#2170)
- [pre-commit.ci] pre-commit autoupdate (#1977)
- Route different content types to correct edit pages (#2169)
- fix: link to external resource rule (#2163)
- fix(deps): update dependency social-auth-app-django to v5.4.1 [security] (#2167)

Version 0.117.0 (Released May 07, 2024)
---------------

- fix(deps): update dependency boto3 to v1.34.90 (#2164)
- Django 4.2.11 / Python 3.12.2 upgrade (#2141)
- Fix runtime errors w/ lmxl + xmlsec (#2161)
- chore(deps): update redis docker tag to v6.2.14 (#2159)
- chore(deps): update postgres docker tag to v12.18 (#2158)
- chore(deps): update postgres docker tag to v11.16 (#2157)
- chore(deps): update node.js to v20.12.2 (#2156)
- chore(deps): update nginx docker tag to v1.25.5 (#2155)
- chore(deps): update docker.elastic.co/elasticsearch/elasticsearch docker tag to v6.8.23 (#2154)
- chore(deps): update dependency turndown to v7.1.3 (#2153)
- fix(deps): update dependency boto3 to v1.34.88 (#2151)

Version 0.116.3 (Released April 24, 2024)
---------------

- Update actions: checkout, setup-python, setup-node, node-version (#2146)

Version 0.116.2 (Released April 18, 2024)
---------------

- Fix: Add nubbins for celery monitoring (#2142)

Version 0.116.1 (Released April 09, 2024)
---------------

- Fix Google Drive copy and adding test (#2131)

Version 0.116.0 (Released April 04, 2024)
---------------

- feat: add link to external resource rules (#2130)
- fix(deps): update dependency express to v4.19.2 [security] (#2136)
- fix(deps): update dependency webpack-dev-middleware to v5.3.4 [security] (#2135)

Version 0.115.0 (Released March 13, 2024)
---------------

- fix: increase timeout for e2e tests (#2128)
- chore(deps): update react monorepo (#1949)
- chore(e2e): update fixtures and fix typo (#2125)

Version 0.114.1 (Released March 05, 2024)
---------------

- use the prefix argument in the hugo baseURL argument during the online build (#2121)

Version 0.114.0 (Released March 05, 2024)
---------------

- Copy videos from one course to another (#2120)
- chore(e2e): update fixtures for external resource tests (#2116)

Version 0.113.0 (Released February 28, 2024)
---------------

- Allow editing and publishing of test sites (#2114)

Version 0.112.1 (Released February 13, 2024)
---------------

- new params (#2109)
- Update dependency ipython to v8.21.0 (#2103)
- Update dependency google-auth-oauthlib to v1.2.0 (#2098)
- Update dependency google-api-python-client to v2.117.0 (#2105)
- Update dependency black to v22.12.0 (#2104)

Version 0.112.0 (Released February 12, 2024)
---------------

- Update dependency django-safedelete to v1.3.3 (#2102)
- allow unicode characters in filenames (#2087)
- Update dependency django-hijack to v3.4.5 (#2101)
- Update dependency cryptography to v41.0.7 (#2100)
- Update dependency boto3 to v1.34.39 (#2099)
- Update dependency google-auth to v2.27.0 (#2097)
- Update dependency tqdm to v4.66.2 (#2096)

Version 0.111.1 (Released February 12, 2024)
---------------

- Update dependency faker to v19.13.0 (#2091)
- Update dependency celery to v5.3.6 (#2093)
- Update dependency beautifulsoup4 to v4.12.3 (#2092)
- Update dependency boto3 to v1.34.38 (#2090)
- Fix S3 path for Google Drive backfill (#2089)

Version 0.111.0 (Released February 06, 2024)
---------------

- Backfill Google Drive folder for legacy courses (#2081)
- Correctly set branch when commit hash is not given (#2083)

Version 0.110.4 (Released January 24, 2024)
---------------

- e2e test pipeline cache clearing (#2078)

Version 0.110.3 (Released January 22, 2024)
---------------

- Multiple open catalog webhook endpoints (#2071)

Version 0.110.2 (Released January 18, 2024)
---------------

- set RESOURCE_BASE_URL regardless of environment (#2073)

Version 0.110.1 (Released January 16, 2024)
---------------

- Fix theme assets pipeline on Apple Silicon (#2069)

Version 0.110.0 (Released January 16, 2024)
---------------

- fix api mocking in e2e test pipeline (#2066)
- fix(deps): update dependency django-webpack-loader to v1.8.1 (#2041)
- fix(deps): update dependency webpack to v5.89.0 (#2037)
- allow sitemap_domain to be overridden in the site pipeline config, and override it in the end to end testing pipeline (#2061)
- fix file path formatting issue in test course data export (#2058)
- chore(deps): update node.js to v20 (#2055)
- feat(management): add broken link fixing cleanup rules (#2050)
- end to end testing pipeline (#2018)

Version 0.109.0 (Released December 20, 2023)
---------------

- management command for importing website starters from GitHub (#2049)

Version 0.108.0 (Released December 11, 2023)
---------------

- unpublished should be a boolean (#2046)
- add exclude filter to management commands (#2035)

Version 0.107.5 (Released December 11, 2023)
---------------

- chore(deps): update dependency pytest to v7.4.3 (#2031)
- fix(deps): update dependency js-beautify to v1.14.11 (#1914)

Version 0.107.4 (Released November 29, 2023)
---------------

- fix(deps): update dependency luxon to v3.4.4 (#1910)
- fix(deps): update dependency @types/pluralize to ^0.0.33 (#1912)

Version 0.107.3 (Released November 20, 2023)
---------------

- Create video workflow documentation (#2010)
- test: improve tests for existing captions (#2026)

Version 0.107.2 (Released November 16, 2023)
---------------

- Fix self-closing shortcodes (#2025)

Version 0.107.1 (Released November 16, 2023)
---------------

- ci: add pull_request trigger (#2020)
- compose file updates (#2023)
- fix(deps): update dependency @reduxjs/toolkit to v1.9.7 (#1995)

Version 0.107.0 (Released November 13, 2023)
---------------

- update FilterWebpackArtifactsStep to support webpack-manifest-plugin (#2017)

Version 0.106.0 (Released October 30, 2023)
---------------

- fix: use transcoded video's size in content (#2009)
- Update dependency @types/node to v16.18.59 (#1911)

Version 0.105.1 (Released October 18, 2023)
---------------

- don't remove videos from the single site online pipeline after the build completes (#2003)

Version 0.105.0 (Released October 17, 2023)
---------------

- root website pipeline improvements (#1999)

Version 0.104.0 (Released October 11, 2023)
---------------

- overhaul unpublish sites pipeline (#1993)

Version 0.103.0 (Released October 05, 2023)
---------------

- use new mass build pipeline (#1990)
- Update dependency @types/lodash to v4.14.199 (#1909)
- add support for specifying prefix to SitePipelineDefinition and MassBuildSitesPipelineDefinition (#1988)

Version 0.102.6 (Released September 26, 2023)
---------------

- Fix italics font size issue in CKEditor (#1984)
- Make return type of is_gdrive_enabled Boolean (#1986)

Version 0.102.5 (Released September 26, 2023)
---------------

- fix ocw-studio-webhook URL in MassBuildSitesPipelineDefinition (#1973)
- allow Pagination in Collaborator List (#1932)
- filter out videos during online mass build (#1963)

Version 0.102.4 (Released September 19, 2023)
---------------

- explicitly check value of IS_ROOT_WEBSITE as an integer and add tests to make sure that is being done (#1979)
- fix static api base url dev override (#1975)

Version 0.102.3 (Released September 18, 2023)
---------------

- Strip extensions before matching videos and captions (#1970)

Version 0.102.2 (Released September 14, 2023)
---------------

- Fix legacy closing shortcodes in CKEditor (#1968)
- Enable Self-Closing Shortcodes (#1961)
- consolidate arguments in new pipeline definitions (#1960)
- ignore the s3 directory when running pytest and black (#1959)

Version 0.102.1 (Released September 12, 2023)
---------------

- optimize site_pipeline_test and mass_build_sites_test (#1953)
- [pre-commit.ci] pre-commit autoupdate (#1955)
- add prettier-django to the ci:skip list in pre-commit (#1956)

Version 0.102.0 (Released September 11, 2023)
---------------

- set check_every: never on SiteContentGitResource (#1951)

Version 0.101.1 (Released September 11, 2023)
---------------

- use new site pipeline definition (#1931)
- update poetry lock file (#1946)
- fix,config: Fix ignore revs file with full commit hash
- config: Add file to ignore pre-commit refactoring in git blame
- config,refactor: Add more extensive pre-commit config and lint rules (#1930)
- fix common pipeline vars (#1937)

Version 0.101.0 (Released September 07, 2023)
---------------

- fix ClearCdnCacheStep (#1944)
- properly clone private repos in SiteContentGitTaskStep (#1935)
- fix non-dev upsert_theme_assets_pipeline (#1941)
- explicitly set inputs to a blank list on put steps that don't need them (#1939)
- overhaul mass build pipeline (#1923)
- use new theme assets pipeline definition (#1929)
- separate concourse web and worker into two containers (#1925)

Version 0.100.0 (Released August 23, 2023)
---------------

- conf: add feature flags for select field (#1921)
- feat: select widget improvements (#1888)
- overhaul site pipeline definition (#1900)

Version 0.99.0 (Released August 02, 2023)
--------------

- Tune uWSGI settings (#1886)

Version 0.98.3 (Released July 31, 2023)
--------------

- Fix draft publishing bug (#1873)
- overhaul theme assets pipeline definition (#1896)
- add uwsgitop using poetry (#1898)

Version 0.98.2 (Released July 27, 2023)
--------------

- remove requirements.txt (#1903)
- Use Poetry for managing Python Dependencies (#1893)
- add ol-concourse common components (#1894)

Version 0.98.1 (Released July 20, 2023)
--------------

- Bump pyyaml to 6.0.1 and yamale to 4.0.4 (#1891)

Version 0.98.0 (Released July 17, 2023)
--------------

- fix: strip '/' from keys in populate_file_sizes (#1879)
- chore: create populate_file_sizes command (#1861)

Version 0.97.1 (Released July 13, 2023)
--------------

- make drivefile size a BigInteger (#1875)
- chore(deps): lock file maintenance (#1866)

Version 0.97.0 (Released July 11, 2023)
--------------

- don't generate or sync zips for the root website (#1865)
- Python 3.10 / Django 3.2 upgrade (#1844)
- chore(deps): lock file maintenance (#1860)

Version 0.96.1 (Released July 06, 2023)
--------------

- Remove url property from menu items if pageRef is set (#1857)
- chore(deps): lock file maintenance (#1850)
- fix a useless test (#1849)

Version 0.96.0 (Released July 05, 2023)
--------------

- GDrive File Size Sync (#1851)

Version 0.95.1 (Released June 21, 2023)
--------------

- Use pageRef with new internal navigation menu items (#1845)
- chore: upgrade actions' versions (#1843)
- chore(deps): update akhileshns/heroku-deploy digest to 9fd0f9f (#1799)

Version 0.95.0 (Released June 21, 2023)
--------------

- enhancement: upgrade publisher (#1826)
- chore(deps): lock file maintenance (#1789)
- Delete PR Template
- update swc (#1842)

Version 0.94.1 (Released June 12, 2023)
--------------

- up timeout on offline build to 90 minutes (#1840)
- ZIPs with and without videos (#1836)
- Update linting, formatting (#1831)
- update typescript to 4.9.5 (#1830)
- fix @types/react versions (#1828)

Version 0.94.0 (Released June 07, 2023)
--------------

- fix: too many upload success emails (#1827)
- Fix a linting issue for renovate (#1823)

Version 0.93.4 (Released May 31, 2023)
--------------

- SENTRY_ENV added to the themes-pipelines (#1811)

Version 0.93.3 (Released May 25, 2023)
--------------

- Use all starters (#1818)

Version 0.93.2 (Released May 23, 2023)
--------------

- template noindex variable into mass-build-sites pipeline (#1817)

Version 0.93.1 (Released May 22, 2023)
--------------

- Adding NOINDEX Variable Definition to Concourse Pipelines (#1813)

Version 0.93.0 (Released May 18, 2023)
--------------

- Sync missing captions - Fixed incorrect file paths (#1809)
- fix: should not delete resources that are being used in a site (#1759)
- Process PDFs with missing metadata (#1808)
- Fixing test result sort order (#1805)
- Fix S3 path for missing captions (#1797)
- Revert "Incorrect files path for Sync missing captions (#1792)" (#1795)
- Updating concourse to v7.9.1 (#1788)
- Incorrect files path for Sync missing captions (#1792)

Version 0.92.1 (Released May 10, 2023)
--------------

- Sync missing captions - File seek(0) (#1772)
- config: Add renovate config for ocw-studio (#1774)

Version 0.92.0 (Released May 08, 2023)
--------------

- move back to governmentpaas/s3-resource for webpack-json for the time being (#1780)
- fix: IntegrityError - duplicate key while creating resources (#1770)
- fix static-resources-subdirectory pathing (#1777)
- separate online and offline parts of site-pipeline into separate jobs (#1763)

Version 0.91.2 (Released May 03, 2023)
--------------

- Accept null strings in fields (#1769)

Version 0.91.1 (Released May 02, 2023)
--------------

- Static_Shared Historical artifacts removed (#1730)

Version 0.91.0 (Released April 27, 2023)
--------------

- fix: delete file error messages are not shown on the frontend (#1762)
- fix: duplicate 3play submissions (#1736)
- Sync missing captions and transcripts (#1717)
- add s3 folder to dockerignore (#1761)

Version 0.90.1 (Released April 24, 2023)
--------------

- support irregular values in archive_url in backpopulate_archive_videos (#1756)

Version 0.90.0 (Released April 20, 2023)
--------------

- missing this one period messed up the pathing (#1750)
- Revert "use a safer strategy for filtering out mp4 files in the offline builds in the single site pipeline (#1742)" (#1749)
- feat: update drive sync and allow file deletion (#1724)
- backpopulate archive videos (#1743)
- use a safer strategy for filtering out mp4 files in the offline builds in the single site pipeline (#1742)
- remove codecov (#1747)

Version 0.89.2 (Released April 10, 2023)
--------------

- [Google Drive] Remove Import Files Task and Make Manual Sync Robust to Changing Folder Name (#1735)
- Added OCW_HUGO_THEMES_SENTRY_ENV to ocw-studio (#1725)

Version 0.89.1 (Released April 06, 2023)
--------------

- Bump redis from 3.5.3 to 4.4.4 (#1729)
- Bump webpack from 5.71.0 to 5.76.0 (#1714)
- Bump ipython from 7.31.1 to 8.10.0 (#1678)
- Bump oauthlib from 3.2.1 to 3.2.2 (#1673)
- Bump http-cache-semantics from 4.1.0 to 4.1.1 (#1669)
- Bump activesupport from 6.0.6 to 6.0.6.1 in /docs (#1663)
- Bump ua-parser-js from 0.7.31 to 0.7.35 (#1734)

Version 0.89.0 (Released April 05, 2023)
--------------

- Bump cryptography from 3.3.2 to 39.0.1 (#1676)
- feat: show short_id in course list select (#1727)

Version 0.88.1 (Released April 03, 2023)
--------------

- Exclude JS Map assets from builds (#1720)
- Bump cookiejar from 2.1.3 to 2.1.4 (#1655)
- Bump certifi from 2020.6.20 to 2022.12.7 (#1606)
- Bump nokogiri from 1.13.9 to 1.13.10 in /docs (#1605)

Version 0.88.0 (Released March 22, 2023)
--------------

- Revert "feat: show short_id in course list dropdown (#1715)" (#1721)
- Revert "Fakhar/1646 exclude assests offline (#1713)" (#1718)
- feat: show short_id in course list dropdown (#1715)
- publish websites in root website (#1705)
- Fakhar/1646 exclude assests offline (#1713)
- Fix: Flaky Frontend Test (#1700)

Version 0.87.2 (Released March 13, 2023)
--------------

- Allow only vtt and webvtt extensions for pre-existing captions (#1711)

Version 0.87.1 (Released March 08, 2023)
--------------

- Remove automatic sync of Google Drive to Studio (#1709)

Version 0.87.0 (Released March 06, 2023)
--------------

- Fix static resources path for root website (#1707)
- fix: site title and short_id shown on unpublish dialog (#1701)
- update example env file (#1697)
- mirror drive s3 upload (#1690)

Version 0.86.2 (Released February 23, 2023)
--------------

- Make sure there is a preceding slash on transcript/caption urls (#1693)
- Associate pre-existing captions with new OCW videos (#1683)
- feat: unpublish sites (#1684)
- allow overriding hugo build arguments (#1674)

Version 0.86.1 (Released February 21, 2023)
--------------

- change offline mass build webpack output to be stored in static_shared (#1687)
- Removed default arguments for source and resource  and added confirmation before updating content metadata command (#1451)

Version 0.86.0 (Released February 15, 2023)
--------------

- remove static folder from offline builds (#1680)

Version 0.85.3 (Released February 10, 2023)
--------------

- Updating testing and formatting link (#1672)

Version 0.85.2 (Released February 09, 2023)
--------------

- Update Missing Captions/Transcripts (#1670)
- add recursive redirects to the draft and live locations in the nginx config for local development (#1668)

Version 0.85.1 (Released February 06, 2023)
--------------

- Fixing S3 paths in captions/transcript sync (#1665)

Version 0.85.0 (Released January 31, 2023)
--------------

- consolidate shared static resources (#1657)
- Adding management command to sync captions/transcripts for any videos missing them from one course to another (#1612)
- Setting copyright date to auto-update (#1660)
- Update concourse to v7.9.0 (#1653)
- Update README.md (#1654)
- Updating pipeline definitions to point at ocw-course-publisher v0.4 (#1647)
- Bump decode-uri-component from 0.2.0 to 0.2.2 (#1603)
- Bump loader-utils from 1.4.0 to 1.4.2 (#1573)
- Bump json5 from 1.0.1 to 1.0.2 (#1639)
- Bump luxon from 2.3.1 to ~2.5.2~ 3.2.1 (#1640)

Version 0.84.1 (Released January 23, 2023)
--------------

- Resource links without forking CKEditor's Link Plugin (#1643)

Version 0.84.0 (Released January 04, 2023)
--------------

- skip syncing offline build if no offline config exists (#1637)
- add offline build to single course pipeline (#1630)

Version 0.83.1 (Released December 22, 2022)
--------------

- abort onReady if no editor (#1629)
- Cc/disallow simul subsup (#1627)
- Subscripts and superscripts (#1588) (#1617)

Version 0.83.0 (Released December 21, 2022)
--------------

- purge cache on build failures; add alerts (#1623)
- update ckeditor to v35 (#1618)
- themes branch argument for theme assets build (#1616)

Version 0.82.4 (Released December 20, 2022)
--------------

- clean publish for individual sites (#1611)
- Revert "update content dispositions (#1380)" (#1615)
- Fixing typo in GDrive creation management command (#1610)
- Modify RelationField to filter out unpublished content if the website property is present (#1604)
- update content dispositions (#1380)

Version 0.82.3 (Released December 06, 2022)
--------------

- Fix Routing in OCW Studio (#1600)

Version 0.82.2 (Released December 02, 2022)
--------------

- Revert "Subscripts and superscripts (#1588)" (#1597)
- Subscripts and superscripts (#1588)

Version 0.82.1 (Released December 01, 2022)
--------------

- mb/ubuntu_version_2 (#1594)
- hardcode github action to ubuntu-20.04, see if it passes ci tests (#1591)
- Adding management command to delete objects with missing type (#1587)

Version 0.82.0 (Released November 29, 2022)
--------------

- change slack-webhook to slack-url var (#1585)
- Issue slack alert when theme assets pipeline fails (#1576)
- use slug and not name (#1582)

Version 0.81.3 (Released November 29, 2022)
--------------

- filter out mp4 files in the offline mass-build-sites (#1579)

Version 0.81.2 (Released November 17, 2022)
--------------

- Update docker-compose to work with Apple Silicon (#1572)

Version 0.81.1 (Released November 16, 2022)
--------------

- Raising an error when 3Play transcript submission fails (#1569)

Version 0.81.0 (Released November 16, 2022)
--------------

- add site_short_id to JSON file serializer (#1566)

Version 0.80.0 (Released November 09, 2022)
--------------

- sentry-dsn added in theme assets pipeline (#1563)

Version 0.79.1 (Released November 07, 2022)
--------------

- use OCW_COURSE_STARTER_SLUG in pipelines (#1560)

Version 0.79.0 (Released November 02, 2022)
--------------

- Management Command for Renaming Files on S3 (#1538)
- Bump nokogiri from 1.13.6 to 1.13.9 in /docs (#1537)
- ocw hugo themes sentry dsn added  (#1548)
- Use registry-image in concourse pipelines (#1553)
- name offline site zip with short_id instead of name (#1546)

Version 0.78.3 (Released November 01, 2022)
--------------

- give db service a static ip on the concourse network, and appropriately rename it from minio-network to concourse-network (#1540)
- Update eslint-config-mitodl (#1536)

Version 0.78.2 (Released October 26, 2022)
--------------

- update yarn install (#1541)
- Bump moment from 2.29.1 to 2.29.4 (#1531)
- Bump terser from 5.12.1 to 5.15.1 (#1530)
- Bump protobuf from 3.17.3 to 3.18.3 (#1508)
- Bump oauthlib from 3.1.1 to 3.2.1 (#1485)

Version 0.78.1 (Released October 19, 2022)
--------------

- Adding management command to unpublish list of course sites (#1529)
- Pt/read title from pdf metadata (#1516)

Version 0.78.0 (Released October 18, 2022)
--------------

- upgrade version of ocw-course-publisher (#1526)

Version 0.77.1 (Released October 13, 2022)
--------------

- Add ckeditor5 math plugin (#1522)

Version 0.77.0 (Released October 11, 2022)
--------------

- Replace `@ts-ignore` with `@ts-expect-error`, and remove most of them (#1520)

Version 0.76.0 (Released October 06, 2022)
--------------

- increase timeout on copy-s3-buckets (#1515)

Version 0.75.2 (Released October 06, 2022)
--------------

- proper pathing for the zip command (#1507)
- use a different method to check if html files exist (#1505)

Version 0.75.1 (Released September 28, 2022)
--------------

- Adding on_error and on_abort notifications to slack. (#1503)
- Provide a more helpful error log message when something goes wrong w/git authentication (#1494)

Version 0.75.0 (Released September 22, 2022)
--------------

- increase timeout on mass-build-sites (#1500)
- Bring back synced_checksum reset for nonpublished sites after a url change (#1496)
- log ckeditor errors and use sentry/react (#1488)
- Adding functionality to search resources by filename (#1487)
- emulate separate turndown instances (#1490)
- Fix WebsiteContent.full_metadata property (#1489)
- ZIP up offline sites in mass-build-sites (#1477)

Version 0.74.0 (Released September 20, 2022)
--------------

- feat: site dependencies shown while course unpublishing (#1468)
- Remove oauth2client (#1466)
- removed underline PR (#1475)

Version 0.73.0 (Released September 08, 2022)
--------------

- In the mass site build, if building for offline, move any HTML files from content to static (#1471)
- mass build starter filter (#1467)

Version 0.72.2 (Released September 07, 2022)
--------------

- Refactor Youtube token generation (#1459)

Version 0.72.1 (Released September 01, 2022)
--------------

- mass-build-sites offline flag (#1453)

Version 0.72.0 (Released August 31, 2022)
--------------

- Pt/draft content warnings (#1456)

Version 0.71.3 (Released August 31, 2022)
--------------

- Bump lxml from 4.6.5 to 4.9.1 (#1416)
- Bump tzinfo from 1.2.7 to 1.2.10 in /docs (#1423)

Version 0.71.2 (Released August 22, 2022)
--------------

- Pt/resource picker tabs (#1448)

Version 0.71.1 (Released August 15, 2022)
--------------

- don't retry the mass build automatically (#1445)
- clean up mass build sites logging (#1442)

Version 0.71.0 (Released August 11, 2022)
--------------

- Setting default language for code blocks to plain text (#1437)

Version 0.70.1 (Released August 10, 2022)
--------------

- GITKEYSSH not GITSSHKEY (#1432)
- alternate theme rendering - mass build pipeline (#1429)

Version 0.70.0 (Released July 28, 2022)
--------------

- add local s3 storage emulation with minio (#1421)

Version 0.69.0 (Released July 27, 2022)
--------------

- Clean up noisy detect-secrets errors (#1425)

Version 0.68.0 (Released July 18, 2022)
--------------

- Set notifySubscribers to False by default for YouTube videos uploaded through Studio (#1418)

Version 0.67.0 (Released July 14, 2022)
--------------

- added resource list to resource picker (#1412)
- Removing UUID v1 from displayed filenames in Edit Resource drawer (#1415)
- added check to filter undefined tabs (#1411)

Version 0.66.0 (Released July 11, 2022)
--------------

- Added a check for site status (#1405)
- Add Filename to Edit Resource Menu When GDrive Sync Enabled (#1406)

Version 0.65.0 (Released June 30, 2022)
--------------

- fixed small error (#1408)
- add management command set_content_metadata_to_default (#1402)

Version 0.64.0 (Released June 21, 2022)
--------------

- Added permission hook for conditional rendering  (#1389)
- Use common mgmt command options for filtering by websites (#1394)

Version 0.63.4 (Released June 10, 2022)
--------------

- Remove log statement (#1400)
- Option to delete existing pipelines in management commands (#1392)
- update generate_item_metadata to optionally use config default value (#1363)
- Show publishing api errors in publishing drawer (#1367)
- remove two unused dependencies (#1360)
- do not emit declaration files (#1293)

Version 0.63.3 (Released June 09, 2022)
--------------

- Updating nginx version in docker-compose to 1.22.0 (#1397)

Version 0.63.2 (Released June 07, 2022)
--------------

- Always set publish fields in publish_website function (#1383)
- Management command & github api tweak to ensure checksums are current (#1390)

Version 0.63.1 (Released June 02, 2022)
--------------

- Adding information to the body of each slack alert to indicate which pipeline + course failed (#1385)

Version 0.63.0 (Released May 31, 2022)
--------------

- add migration to move metadata description on resources to the markdown body (#1382)

Version 0.62.1 (Released May 31, 2022)
--------------

- Bump pyjwt from 2.1.0 to 2.4.0 (#1374)
- Bump nokogiri from 1.12.5 to 1.13.6 in /docs (#1334)
- Show proper urls on the Publish Drawer (#1377)
- Fix conflicting migrations (#1378)
- feat: Limit site starter options when creating new site (#1355)
- allow setting link / embed on minimal markdown editor (#1364)

Version 0.62.0 (Released May 25, 2022)
--------------

- Custom URL tweaks (#1371)
- added command to update departments (#1256)
- Added slack notifications on_failure cases to the individual site pipelines. (#1358)
- Customizable URLs for studio (#1316)
- improve legacy shortcode handling (#1349)

Version 0.61.1 (Released May 17, 2022)
--------------

- treat shortcodes in resource link text as literal text (#1359)
- make markdown editor minimal by default (#1351)
- short ID added with title in sites list (#1346)
- check for 3play completion (#1345)
- improve frontend shortcode regex to not be fooled by delimiters in shortcode args (#1347)

Version 0.61.0 (Released May 17, 2022)
--------------

- Hid Site Dashboard and refactored component (#1332)
- use anchor not link for external link (#1341)

Version 0.60.3 (Released May 16, 2022)
--------------

- add VIDEO_S3_TRANSCODE_ENDPOINT (#1324)
- Update the prod deploy script to point to prod (#1333)
- Added a github action for production releases. (#1331)
- make retry_on_failure preserve type hints (#1313)

Version 0.60.2 (Released May 12, 2022)
--------------

- Fix deploy configuration
- add API_BEARER_TOKEN to the Hugo step in the site build pipelines (#1329)
- use the proper ocw-course-publisher image and specify version (#1326)

Version 0.60.1 (Released May 11, 2022)
--------------

- update references to the mitodl/ocw-course-publisher docker container to specify version and set it to 0.2 (#1321)
- Fix workflow syntax (#1319)
- updated node version (#1310)
- Added a github action workflow for releasing to CI
- migrate ocw-www content type pages to page (#1312)
- add SITEMAP_DOMAIN to the app and pipeline templates (#1306)

Version 0.60.0 (Released May 11, 2022)
--------------

- make legacy uid hidden (#1304)

Version 0.59.3 (Released May 09, 2022)
--------------

- fix webvtt transcript (#1302)
- redirect to login on authentication failures (#1300)
- Set up one of the transcoded video outputs to be downloadable (#1288)

Version 0.59.2 (Released May 06, 2022)
--------------

- Cc/user store (#1297)

Version 0.59.1 (Released May 04, 2022)
--------------

- Remove stray slash from unpublish pipeline (#1291)

Version 0.59.0 (Released May 03, 2022)
--------------

- Fix mass publish command (#1289)
- Update social auth readme docs (#1284)
- specify yarn version for heroku (#1266)
- rename migration (#1286)
- Unpublish sites - backend code (#1270)
- add migration to move filetype to resourcetype (#1276)
- Fix file paths command (#1261)
- publish alert, prettier prompt, new IntegrationTestHelper
- fix transcript links (#1281)

Version 0.58.0 (Released April 29, 2022)
--------------

- fix erroneous prompting when saving new pages (#1279)
- Added video-gallery to add link ResourceDialogPicker (#1273)
- Added a check to return as soon as filter_set has been gone over (#1257)
- Prompt for confirmation when discarding changes
- New sites API: Filter out sites without sitemetadata content instead of Website.metadata (#1202)

Version 0.57.6 (Released April 25, 2022)
--------------

- added command to migrate testimonials to stories (#1250)
- Sync Website.title with the sitemetadata course_title (#1244)

Version 0.57.5 (Released April 21, 2022)
--------------

- set `YT_FIELD_DESCRIPTION` to `video_metadata.youtube_description` (#1253)
- Escape quotes in resource link text (#1249)

Version 0.57.4 (Released April 20, 2022)
--------------

- [markdown cleanup] <, > to «, » (#1245)
- Rename mass-publish pipeline to mass-build-sites, refactor mass-publish command (#1246)
- [markdown cleanup] fix superscript/subscript escaping issues (#1241)
- fix: course_collections renamed to course-collection (#1239)

Version 0.57.3 (Released April 15, 2022)
--------------

- fix: required=true for relation widgetvariant (#1240)

Version 0.57.2 (Released April 12, 2022)
--------------

- improve link logging (#1235)

Version 0.57.1 (Released April 12, 2022)
--------------

- remove delete_unpublished_courses (#1234)
- Update filter for the mass-publish api endpoint (#1229)
- Sync videos from Google Drive files_final folder, don't transcode or upload to Youtube (#1227)
- Avoid unnecessary dupe transcode jobs, retry on gdrive->s3 upload errors a few times before raising (#1219)
- Preserve querystrings when paginating (#1226)

Version 0.57.0 (Released April 11, 2022)
--------------

- Allow selection of null values for website publish fields in Django admin (#1224)

Version 0.56.4 (Released April 08, 2022)
--------------

- Cc/default active tab (#1216)
- prevent mass import (#1214)
- add "other" tab to resource picker (#1210)

Version 0.56.3 (Released April 07, 2022)
--------------

- Cc/convert link wrapped images (#1206)

Version 0.56.2 (Released April 05, 2022)
--------------

- Sort websites by first_published_to_production (#1204)

Version 0.56.1 (Released April 05, 2022)
--------------

- update fastly vars for mass-publish pipeline definition (#1199)
- Revert API change (#1200)
- Handle courses with no instructors (#1196)
- Get gdrive file body via the google drive api and stream that to s3 (#1169)
- tolerate href, href_uid on resource shortcode (#1192)
- Use first_published_to_production instead of publish_date for sorting new courses, get metadata from WebsiteContent (#1191)

Version 0.56.0 (Released April 04, 2022)
--------------

- Added some metrics for celery task completion time

Version 0.55.2 (Released March 31, 2022)
--------------

- replace ocwnext with ocw (#1185)
- handle links/images inside links correctly (#1178)
- Convert more baseurl links to resource_links  (#1174)

Version 0.55.1 (Released March 30, 2022)
--------------

- Use get_redis_connection("redis").client() instead of app.backend.client (#1181)
- Fix rootrelative URLs to duplicate files

Version 0.55.0 (Released March 28, 2022)
--------------

- Set a configurable limit to the number of redis pool connections (#1170)
- don't update fields that don't exist in resource data (#1166)

Version 0.54.4 (Released March 28, 2022)
--------------

- set parent_id when overwriting metadata.parent_uid (#1115)
- use pyparsing for link paring + resolveuid fix
- remove image inacessible (#1158)

Version 0.54.3 (Released March 24, 2022)
--------------

- changed italic delimiter to "*" (#1147)

Version 0.54.2 (Released March 23, 2022)
--------------

- Fix gdrive import for ocw-www (#1155)
- fix a typo in the localdev config
- only query with published = true if cross_site is also true (#1109)

Version 0.54.1 (Released March 22, 2022)
--------------

- Use pyparsing for some markdown replacements

Version 0.54.0 (Released March 21, 2022)
--------------

- tweak internal site search (#1134)
- Handle authentication for Concourse 7.7 (#1120)
- tolerate quotes around resource, resource_link uuids (#1136)
- add localdev support for course collection, list
- fix a small issue with the website search

Version 0.53.5 (Released March 17, 2022)
--------------

- Allow mass-publish to process a list of site names from a json file or comma-delimited string (#1127)

Version 0.53.4 (Released March 17, 2022)
--------------

- Option to sync a specific commit/path from github to the database (#1108)
- add inline code support to ckeditor

Version 0.53.3 (Released March 16, 2022)
--------------

- default metadata to empty object before iterating in seralizer (#1129)

Version 0.53.2 (Released March 15, 2022)
--------------

- theme assets build cache busting take 3 (#1121)

Version 0.53.1 (Released March 15, 2022)
--------------

- cc/fix-relative-metadata-links

Version 0.53.0 (Released March 14, 2022)
--------------

- Revert "theme assets build cache busting take 2 (#1103)" (#1117)
- theme assets build cache busting take 2 (#1103)

Version 0.52.2 (Released March 09, 2022)
--------------

- Improved site search for names, short_ids (#1092)
- Fix / Convert rootrelative urls (#1086)

Version 0.52.1 (Released March 09, 2022)
--------------

- Revert "purge theme assets after deployment (#1090)" (#1096)
- merge new metadata with old metadata (#1094)
- purge theme assets after deployment (#1090)

Version 0.52.0 (Released March 08, 2022)
--------------

- adjust PR template
- add code block support to CKEditor
- Add option to add new content and modify nested metadata for overwrite_ocw_course_content command (#1071)

Version 0.51.0 (Released March 03, 2022)
--------------

- fix spacing issue w/ single-line text inside of table cells

Version 0.50.0 (Released March 02, 2022)
--------------

- fix line break in table cells issue

Version 0.49.0 (Released March 02, 2022)
--------------

- move website content drawer open / close / edit state to URL
- change resource_link delimiters to % instead of < > (#1067)
- pass the --buildDrafts argument to Hugo if building a preview (#1062)

Version 0.48.0 (Released March 01, 2022)
--------------

- When syncing from git to db, `file` value should only include the path, not domain (#1056)

Version 0.47.9 (Released February 25, 2022)
--------------

- encode data-uuid passed to CKEditor (#1063)
- Add metadata to mediaconvert job for filtering, based on queue name (#1018)
- Cc/collections limited (#1055)
- Add open webhook to pipelines (#1028)
- Update ContentSyncState checksums when bulk updating WebsiteContent (#1047)
- convert baseurl links w/ fragments (#1036)
- Enforce youtube length limits when uploading/updating title, description (#1009)

Version 0.47.8 (Released February 24, 2022)
--------------

- Enable linking to resource and course collections
- add content filtering to the website content listing page

Version 0.47.7 (Released February 23, 2022)
--------------

- support resource link anchor IDs

Version 0.47.6 (Released February 18, 2022)
--------------

- baseurl replacement improvements (#1034)
- Separate celery queues for publish tasks, batch tasks (#1031)
- Handle youtube 403s and update website publish status immediately on errors (#1007)

Version 0.47.5 (Released February 18, 2022)
--------------

- add GTM_ACCOUNT_ID to OCW site builds (#1027)
- add 'published' param to content listing API

Version 0.47.4 (Released February 17, 2022)
--------------

- add markdown cleanup rule for legacy data fix (#1024)
- Make embeddable=True explicit when updating youtube metadata status (#1022)
- convert resource_file to resource shortcodes (#1016)

Version 0.47.3 (Released February 17, 2022)
--------------

- add support for nondestructive editing w/ legacy shortcodes

Version 0.47.2 (Released February 17, 2022)
--------------

- Only update metadata for youtube videos with associated VideoFile objects (#1014)
- add management command markdown_cleanup_baseurl (#1002)
- small tech debt thing
- improvements to the site search

Version 0.47.1 (Released February 15, 2022)
--------------

- type -> ocw_type (#1004)
- improvements to search handling on the Website listing API
- Blank _logo.html to remove default logo image (#997)

Version 0.47.0 (Released February 14, 2022)
--------------

- Prevent endlessly incrementing short-ids on imported sites, new command to fix affected sites (#988)

Version 0.46.0 (Released February 14, 2022)
--------------

- When resetting sync state, the data field should also be set to None (#946)

Version 0.45.0 (Released February 11, 2022)
--------------

- fix: youtube video thumbnail 0.jpg replaced with default.jpg (120x90) (#985)
- set serial: true on the mass publish job (#987)
- remove italicization of text within blockquote tags in CKEditor
- Setting the resources for the individual sites to `check_every: never`. See https://concourse-ci.org/resources.html. This makes sense because the individual pipelines will now only ever be triggered by webhooks (`trigger: false` is set on all of them). (#982)
- add OCW_IMPORT_STARTER_SLUG to the mass publish pipeline definition code (#984)

Version 0.44.1 (Released February 10, 2022)
--------------

- import for learning_resource_types (#980)

Version 0.44.0 (Released February 08, 2022)
--------------

- copy webpack.json into base-theme instead of into the site's data folder (#977)

Version 0.43.1 (Released February 04, 2022)
--------------

- refactor logic for indicating the site content form has been touched
- Fix pipeline webhook (#970)
- Codify new mass publish pipeline and api endpoint (#950)
- scroll to form errors on submission (#962)
- use governmentpaas/s3-resource for the webpack-json resource to be compatible with using versioned_file with IAM authentication (#966)
- Bump ipython from 7.19.0 to 7.31.1 (#920)
- fix up our handling of the camelcase eslint rule a little bit
- add webpack-json as an input to the build-course-task pipeline step (#961)
- [UI] prevent duplicate items in collections (#951)
- theme assets pipeline (#945)
- remove a @ts-ignore
- small rename of two functions for clarity

Version 0.43.0 (Released January 31, 2022)
--------------

- add yarn.lock
- only make clickable list items have cursor pointer
- remove unused css class card-content
- use margins to separate list items, not padding
- fix issue with website name not being saved in resource collection
- reconcile ckedidtor, showdown multiline list items
- add an optional filter to the website listing API for publish status

Version 0.42.3 (Released January 28, 2022)
--------------

- move pipeline api callbacks to jgriff/http-resource (#937)
- update postgres to 12.8 to match prod

Version 0.42.2 (Released January 27, 2022)
--------------

- Add option of github authentication via app (#914)

Version 0.42.1 (Released January 26, 2022)
--------------

- Upgrade celery (#919)
- move comment above declaration
- move regex back up
- support merging of table cells (#899)
- fix resource_link regex, make non-greedy
- update handling of publish_date field on the Website model

Version 0.42.0 (Released January 25, 2022)
--------------

- ocw_import_course_sites - sync to github by default (#921)
- some test cleanup
- enable linking to pages within a course

Version 0.41.1 (Released January 21, 2022)
--------------

- Limit git api rate for all current batch functions that use it at high volume (#909)

Version 0.41.0 (Released January 20, 2022)
--------------

- remove 'legacy' implementation of WebsiteCollections

Version 0.40.1 (Released January 18, 2022)
--------------

- add -p to mkdir command before theme asset extraction (#900)

Version 0.40.0 (Released January 13, 2022)
--------------

- "waterfall" triggering scheme for ocw-hugo-themes changes (#891)
- switch from storing website UUID to the website name property
- add support for 'website-collection' field

Version 0.39.1 (Released December 23, 2021)
--------------

- Revert "use static version file as trigger for sites other than ocw-www (#881)" (#883)
- use static version file as trigger for sites other than ocw-www (#881)

Version 0.39.0 (Released December 21, 2021)
--------------

- Retry all pipeline steps up to 3x (#864)
- Descriptive message on front end for publishing warnings (#867)
- add uids to metadata output
- Fix a bad query (#877)

Version 0.38.0 (Released December 20, 2021)
--------------

- Fix task bug caused by decorator (#873)
- Fix Youtube API status update call (#875)
- Bump lxml from 4.6.3 to 4.6.5 (#868)
- Split sortable UI off from RelationWidget into SortableSelect component
- Run incomplete_publish_build_statuses task only if a pipeline backend is set (#851)
- set up swc for jest, webpack
- Bump django from 3.1.13 to 3.1.14 (#866)
- Log an error when a pipeline fails (#854)
- Make youtube videos public for live publishing (#850)
- remove an unused dependency
- Fix outdated starter configs, add README instructions to update them via mgmt command (#858)
- Avoid certain WebsiteContent filenames (#855)
- Concourse in a docker container (#852)
- add site search

Version 0.37.5 (Released December 14, 2021)
--------------

- Add all metadata keys w/blank values for imported google drive content (#860)

Version 0.37.4 (Released December 09, 2021)
--------------

- refactor fix for deleting orphaned git files (#849)
- import video galleries (#848)
- Do not show menu dropdown for global admins or site owner (#844)
- Remove old pages and content (#843)

Version 0.37.3 (Released December 03, 2021)
--------------

- use task decorator to prevent multiple instances of recurring scheduled tasks from running at once (#832)
- Populate additional fields when publishing via mass_publish (#840)
- move from casual-browserify to the normal package

Version 0.37.2 (Released December 02, 2021)
--------------

- update typescript a little bit
- upgrade ckeditor packages to the latest version
- Use concourse webhooks plus periodic task to update publish status (#820)
- make title the default text inside of a resource link
- Ignore anything in parentheses for short_id (#830)
- remove Dockerfile-node
- remove an unnecessary step from our CI setup
- fix callback url
- conditionally set the modal titlee on menu page for editing, adding
- Remove some unnecessary mocks of `global.fetch`

Version 0.37.1 (Released November 30, 2021)
--------------

- add cross_site option to the Relation field
- Fix publish bug (#821)
- Add option to delete git files not matching WebsiteContent in db (#812)
- Handle all cases of youtube_id being null (#816)
- Mass publish sites management command (trigger_pipelines -> mass_publish) (#801)
- Fix changing short_id on ocw reimport, reset publish fields as part of `reset_sync_state` command (#809)
- Show confirmation dialog when data would be lost (#799)
- Always unpause pipelines before triggering (#811)

Version 0.37.0 (Released November 19, 2021)
--------------

- transcript notifications

Version 0.36.0 (Released November 15, 2021)
--------------

- Create gdrive folders for imported sites if unassigned (#798)
- Fix some issues with upserting multiple site pipelines (#794)

Version 0.35.1 (Released November 12, 2021)
--------------

- automate transcript upload
- Trigger concourse build via API (#783)

Version 0.35.0 (Released November 09, 2021)
--------------

- fix an issue with the migration to deal with bad data (#787)
- Poll for gdrive folder if blank on resources page (#781)
- Update various pages to use new, Card-based designs
- make sure menu items never have zero weight (#775)
- Tweak WebsiteContent permissions (#772)
- Send publish email within polling task and only to the publish requester (#766)
- upgrade to yarn 3
- Fix several celery task bugs (#774)
- add a 404 page for a missing site
- add page titles

Version 0.34.0 (Released November 08, 2021)
--------------

- Sync status frontend (#758)
- Handle level import, add term and year to metadata (#757)

Version 0.33.0 (Released November 02, 2021)
--------------

- add error handling to the Relation field request
- Fix poll_build_status_until_complete to use celery countdown instead of sleep (#763)

Version 0.32.2 (Released November 02, 2021)
--------------

- add ocw-www site dependency to readme
- fix image alignment issue
- Filter resourcetype on backend for website content (#742)
- add support for editing table shortcodes to the markdown editor
- Track sync status backend, w/fixed migration (#751)

Version 0.32.1 (Released November 01, 2021)
--------------

- Change ContentDisposition for videos
- Revert "Track website sync status - backend (#734)" (#750)
- Track website sync status - backend (#734)
- Upgrade sentry (#697)
- Fix flaky test (#739)
- Privacy policy page and home page tweaks (#737)
- Implement publish status UI (#705)
- switching over a bunch of test files to use the new mockRequest functions

Version 0.32.0 (Released October 28, 2021)
--------------

- Open publish site links in new tab (#729)
- Show google drive links (#720)
- Use name instead of short_id for resource S3 keys (#726)
- add to validation schema, add an example thing in there

Version 0.31.0 (Released October 22, 2021)
--------------

- Make check for rate limits optional in sync_unsynced_websites task (#721)
- Slugify s3 keys and make sure they're still unique (#710)
- Hide production publish btn, prohibit metadata editing for non-admin editors (#702)
- Hide the file upload field on resource form if google drive integration is enabled (#712)
- add a line to .gitignore
- update ocw_import (#715)
- Fix flaky test (test_format_recipient) (#713)
- small fix for UX issue on website collections page
- Fix bug in create_gdrive_folders (#704)

Version 0.30.4 (Released October 18, 2021)
--------------

- remove title from hugo menu serialization (#703)
- remove some unneeded testing code

Version 0.30.3 (Released October 14, 2021)
--------------

- Updated common UI elements and basic page layout to match new designs
- disallow nested tables

Version 0.30.2 (Released October 13, 2021)
--------------

- fix issue preventing opening MenuField dialog

Version 0.30.1 (Released October 13, 2021)
--------------

- use theme assets from RC for now (#686)
- Update website publish date for singleton content (#684)
- Copy gdrive mime_type to file_type in content  metadata (#683)
- Added redesigned site header

Version 0.30.0 (Released October 12, 2021)
--------------

- Ignore drive folders with no download links, handle null checksums (#666)
- Fix google drive sync bug with pages (#676)
- Do a hard or soft fastly purge based on settings (#671)
- Autocreate all gdrive resources, fix github syncing for them (#630)
- Leave new pipelines paused until previewed/published for the first time (#662)

Version 0.29.2 (Released October 12, 2021)
--------------

- add tables to CKEditor config for Markdown editor #645
- Ensure that delete_unpublished_courses runs only after all courses have finished importing (#649)
- Dont instantiate the YouTubeAPI class unless it has something to do (#661)
- update url-assembler typedef so we can remove @ts-ignore
- change how URL matching works in IntegrationTestHelper
- Set site-id metadata during pipeline s3 sync (#660)
- Use text_id from frontend when creating WebsiteContent (#656)
- prefix destination urls with / to make them root relative (#657)

Version 0.29.1 (Released October 07, 2021)
--------------

- Site publish drawer (#623)
- Management command for resetting synced checksums and optionally syncing all github repos (#644)
- when serializing Hugo markdown files, write out the WebsiteContent type property as content_type and deserialize that back into type (#646)
- Save file location to WebsiteContent.file for imported OCW courses (#635)
- style / layout / ux updates to the resource picker
- Bump nokogiri from 1.11.4 to 1.12.5 in /docs (#610)
- Bump django from 3.1.12 to 3.1.13 (#595)

Version 0.29.0 (Released October 04, 2021)
--------------

- Tweak s3 path for gdrive-imported nonvideo files (#611)
- Additional env variables for concourse pipelines (#632)

Version 0.28.0 (Released October 01, 2021)
--------------

- Fix bug so slug field is used for filename (#625)
- Trim content from destination url (#627)
- import additional metadata (#622)
- remove unnecessary changes to the webpack config
- allow users to create inline links to resources
- remove media embed plugin button from Markdown editor toolbar
- Rename duplicate names during ocw-import (#603)
- Front-end for google drive syncing (#604)
- dependency upgrade
- Sync all files in Google Drive (#591)
- Add slug field to set a different value for filenames of content (#600)

Version 0.27.0 (Released September 28, 2021)
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
