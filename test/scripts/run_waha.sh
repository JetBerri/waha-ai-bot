if [ -z "$(docker images -q myimage:mytag 2> /dev/null)" ]; then

    docker pull --platform linux/x86_64 devlikeapro/waha:latest

fi

docker run -it --rm --network=host -e WHATSAPP_HOOK_URL=http://localhost:5000/bot -e "WHATSAPP_HOOK_EVENTS=*" --name waha devlikeapro/waha