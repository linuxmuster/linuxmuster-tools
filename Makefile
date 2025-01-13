all: build

deb:
	dpkg-buildpackage -rfakeroot -tc -sa -us -uc -I".gitignore" -I".git" -I".github" -I"docs" -I"docs_src"

doc:
	sphinx-build -b html -d docs/doctrees  docs_src docs
