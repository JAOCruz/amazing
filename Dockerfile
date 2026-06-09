FROM odoo:18.0-20250725

USER root

RUN apt-get update && apt-get install -y curl ca-certificates gnupg --no-install-recommends \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /dgii-sign
COPY addons/l10n_do_ecf_invoicing/scripts/sign_generic.mjs /dgii-sign/sign_generic.mjs
COPY addons/l10n_do_ecf_invoicing/scripts/sign_generic_sha1.mjs /dgii-sign/sign_generic_sha1.mjs

WORKDIR /dgii-sign
RUN npm install dgii-ecf

USER odoo
