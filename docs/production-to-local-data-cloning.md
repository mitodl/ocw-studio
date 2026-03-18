# Cloning Data from Production for Local Development

First, follow the [Platform Engineering guide](https://pe.ol.mit.edu/getting_started/developer_eks_access/) for getting set up with EKS credentials. In particular, run `login_helper.py` and generate `AWS` credentials and the `kubeconfig` file.

Once this is complete, run `kubectl get secret -n ocw-studio postgres-ocw-studio-dynamic-secret -o jsonpath='{.data.DATABASE_URL}' | base64 --decode; echo` to get the `DATABASE_URL` for the production data. Then, create an ephemeral pod for cloning the data by running the following:

```
kubectl run pg-client-<your name> \
  --image=postgres:18 \
  --restart=Never \
  -n ocw-studio \
  --command -- sleep 3600
```

Wait for the ephemeral pod to be ready:

```
kubectl wait --for=condition=Ready pod/pg-client-<your name> -n ocw-studio --timeout=120s
```

Once this returns with `condition met`, open a shell:

```
kubectl exec -it -n ocw-studio pg-client-<your name> -- sh
```

Then, in the ephemeral pod, run

```
export DATABASE_URL=<DATABASE_URL obtained earlier>
pg_dump "$DATABASE_URL" | gzip > /tmp/prod_<today's date>.sql.gz
exit
```

Next, copy the data to your local machine with

```
kubectl cp ocw-studio/pg-client-<your name>:/tmp/prod_<today's date>.sql.gz ./prod_<today's date>.sql.gz
```

Uncompress the data with

```
gunzip prod_<today's date>.sql.gz
```

Verify that the data is now present locally, and then delete the ephemeral pod by running

```
kubectl delete pod -n ocw-studio pg-client-<your name>
```

Next, actually import the data into OCW Studio by running

```
docker compose rm -sv db
docker compose up -d db
docker compose exec -T -e PGPASSWORD=postgres db psql -h db -U postgres < ./prod_<today's date>.sql
```

It is important to note that the Google Drive folders in the local data will be pointing to production Google Drive folders, which is not what should be used for local development. They should instead be set to RC folders by running the following in a Django shell (obtained by running `docker compose exec web ./manage.py shell`):

```
from websites.models import Website
Website.objects.all().update(gdrive_folder=None)
```

Finally, run the management command to associate the sites with the RC Google Drive folders:

```
docker compose exec web ./manage.py create_missing_gdrive_folders
```
