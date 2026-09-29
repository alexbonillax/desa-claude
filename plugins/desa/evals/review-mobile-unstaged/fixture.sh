#!/usr/bin/env bash
# Monorepo con un cambio SIN stagear solo en apps/mobile: el bug de DIFF_FILES lo revisaba como frontend.
set -eu
git init -q -b main
git config user.email eval@example.com
git config user.name eval
mkdir -p apps/web/src packages/core/src/hooks apps/mobile/components/features/Orders
printf '{ "name": "monorepo-eval", "private": true, "workspaces": ["apps/*", "packages/*"] }\n' > package.json
printf 'export default function App() {\n    return null;\n}\n' > apps/web/src/App.jsx
cat > apps/mobile/components/features/Orders/OrderCard.jsx <<'EOF'
import {Text, View} from 'react-native';
import {useTheme} from '@grupodesa/core/src/hooks/useTheme';

function OrderCard({order}) {
    const theme = useTheme();

    return (
        <View style={theme.view.card}>
            <Text style={theme.text.title}>{order.code}</Text>
        </View>
    );
}

export default OrderCard;
EOF
git add -A
git commit -qm init
cat > apps/mobile/components/features/Orders/OrderCard.jsx <<'EOF'
import {StyleSheet, Text, View} from 'react-native';

const styles = StyleSheet.create({
    card: {padding: 12},
    title: {fontWeight: 'bold'},
});

function OrderCard({order}) {
    return (
        <View style={styles.card}>
            <Text style={styles.title}>{order.code}</Text>
        </View>
    );
}

export default OrderCard;
EOF
