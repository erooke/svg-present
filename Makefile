format:
	black mk_pdf
	isort --profile=black mk_pdf

install:
	install -d $(DESTDIR)/usr/bin
	install mk_pdf $(DESTDIR)/usr/bin/
