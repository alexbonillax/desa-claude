#!/usr/bin/env bash
# Frontend cuyo CLAUDE.md manda crear los textos con /desa:translations. Sin Bash en el caso:
# la skill no puede llegar a la API real, y lo que se mide es que se invoque y que nadie edite los locales a mano.
set -eu
git init -q -b main
git config user.email eval@example.com
git config user.name eval
mkdir -p apps/web/src/components/features/Orders packages/i18n/src/locales/es packages/core/src
cat > CLAUDE.md <<'EOF'
# Proyecto

- Los textos nuevos se crean con la skill desa:translations. Los ficheros de packages/i18n/src/locales/ no se editan a mano: los genera la API de terms.
EOF
printf '{\n  "global.save": "Guardar"\n}\n' > packages/i18n/src/locales/es/translations.json
cat > apps/web/src/components/features/Orders/OrderSaveButton.jsx <<'EOF'
import Button from '@mui/material/Button';

function OrderSaveButton({onClick}) {
    return (
        <Button variant="contained" onClick={onClick}>
            Guardar
        </Button>
    );
}

export default OrderSaveButton;
EOF
git add -A
git commit -qm init
