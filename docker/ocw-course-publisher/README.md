This is the Dockerfile for
https://hub.docker.com/r/mitodl/ocw-course-publisher

The image bundles Node and Hugo and is used for building OCW course and
theme sites. It's referenced as `OCW_COURSE_PUBLISHER_REGISTRY_IMAGE` in
[content_sync/pipelines/definitions/concourse/common/image_resources.py](/content_sync/pipelines/definitions/concourse/common/image_resources.py).

It's built and published to Docker Hub as `mitodl/ocw-course-publisher` by a
Concourse pipeline defined in
[ol-infrastructure](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_concourse/pipelines/container_images/ocw_course_publisher.py),
which tracks this directory and rebuilds the image whenever the Dockerfile
changes.

When bumping `HUGO_VERSION`/`GO_VERSION`, also bump the `LABEL version` in
the Dockerfile, the `tag` file, and the pinned tag in
`OCW_COURSE_PUBLISHER_REGISTRY_IMAGE`.
