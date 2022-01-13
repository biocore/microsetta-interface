#!/bin/bash

cwd=$(pwd)
export MICROSETTA_INTERFACE_DEBUG_JWT_PUB=${cwd}/jwtRS256.key.pub
export MICROSETTA_INTERFACE_DEBUG_JWT_PRIV=${cwd}/jwtRS256.key

# based on https://gist.github.com/ygotthilf/baa58da5c3dd1f69fae9
# and https://unix.stackexchange.com/a/69318
ssh-keygen -t rsa -b 4096 -m PEM -f ${MICROSETTA_INTERFACE_DEBUG_JWT_PRIV} -N ""
openssl rsa -in ${MICROSETTA_INTERFACE_DEBUG_JWT_PRIV} -pubout -outform PEM -out ${MICROSETTA_INTERFACE_DEBUG_JWT_PUB}
