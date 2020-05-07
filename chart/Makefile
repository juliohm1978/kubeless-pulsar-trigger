index: package
	cd ../chart-index && helm repo index .

push: index
	cd ../chart-index && git add . && git commit -m 'chart update' && git push

package:
	cd ../chart-index && helm package ../chart/kubeless-pulsar-trigger
