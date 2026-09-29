#!/usr/bin/env bash
# Proyecto Next.js single-app (tipo websites): antes /desa:plan terminaba en «unknown».
set -eu
git init -q -b main
git config user.email eval@example.com
git config user.name eval
mkdir -p src/api/services src/hooks src/lib
printf '{ "name": "websites-eval", "private": true, "dependencies": { "next": "16.0.0" } }\n' > package.json
printf 'module.exports = {};\n' > next.config.js
cat > src/api/api.js <<'EOF'
export const REVALIDATE = {SITE: 300, CATEGORIES: 300, COLLECTIONS: 60, POST: 5};

async function request(path, {revalidate} = {}) {
    const response = await fetch(`${process.env.NEXT_PUBLIC_ENV_API_URL}${path}`, {next: {revalidate}});
    return response.ok ? response.json() : null;
}

export const get = (path, options) => request(path, options);
EOF
cat > src/api/services/SitesService.js <<'EOF'
import * as api from '../api';

export const get = (siteId) => api.get(`/sites/${siteId}`, {revalidate: api.REVALIDATE.SITE});
EOF
cat > src/hooks/useLocale.js <<'EOF'
import {useParams} from 'next/navigation';

const useLocale = () => useParams().locale ?? 'es';

export default useLocale;
EOF
git add -A
git commit -qm init
