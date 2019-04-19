## Docker Registry Synchronizer

This helper project will synchronize Docker image from popular public Docker Registry services to your own registry.

* Support gcr.io, quay.io and Docker Hub
* Support public source image from above registry services only
* Sync the tagged images from given repo updated within 15 days (default)


### Prequesite

```
pip install docker
pip install python-dateutil
pip install requests[security]
```

### Editing image lists
Edit the images.txt of the image repositories for syncing

```
quay.io/coreos/prometheus-operator=registry.cn-hangzhou.aliyuncs.com/coreos_containers/prometheus-operator
gcr.io/google_containers/pause-amd64

```

Each line will be one repo definition

```source_repo=target_repo``` Sync the source repo to specific target repo

or

```source_repo``` Sync the source repo to default target repo, which is using default registry, namespace and the same name of the source repo.

In case to sync private repos of aliyun registry cross regions, you have to configure your aliyun cli before you get start, pls refer to [aliyun-cli](https://help.aliyun.com/document_detail/110341.html?spm=a2c4g.11186623.6.544.262e17a4ZH9dOt)

```
registry.cn-hangzhou.aliyuncs.com/eric-dev/debug=registry.ap-southeast-1.aliyuncs.com/eric-dev/debug
```

### Usage

Help

```sh
python sync_images.py -h|--help
```

Synchronize images from the configuraiton files, by default "images.txt"

```sh
python sync_images.py
```

Other optional arguments


```sh
-f|--file <image_list_file>
-r|--registry <host:port> Default "registry.cn-hangzhou.aliyuncs.com"
-n|--namespace <namespace> Default "google_containers"
-d|--days <days> Default 15
```

### Remove out-of-date images

You can run the following command to remove the images created more than 30 days (720h) ago:

```sh
docker image prune -a --force --filter "until=720h"
```
