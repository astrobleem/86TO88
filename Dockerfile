# Serves the same static one-click page as https://astrobleem.github.io/86TO88/
# Usage:  docker build -t 86to88 . && docker run --rm -p 8080:80 86to88
# Then open http://localhost:8080/ in a desktop browser.
# The image contains no Microsoft software and no ROMs; the page downloads
# hash-pinned public reference media in the visitor's browser, as on Pages.
FROM nginx:1.27-alpine
COPY site/ /usr/share/nginx/html/
EXPOSE 80
