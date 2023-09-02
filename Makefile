all: build

deb:
	dpkg-buildpackage -rfakeroot -tc -sa -us -uc -I".gitignore" -I".git" -I".github"

