#!/bin/bash
case \$1 in
  vast) docker run -d --restart=always -p 8000:80 nginx ;;
esac
