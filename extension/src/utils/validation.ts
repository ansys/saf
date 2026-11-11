// Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
// SPDX-License-Identifier: Apache-2.0
//

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


export function isValidVersionConstraint(version: string): boolean {
    const validPatterns = [
        /^\d+\.\d+\.\d+$/, // Exact version: 1.0.0
        /^>=\d+\.\d+\.\d+$/, // Greater than or equal: >=1.0.0
        /^<=\d+\.\d+\.\d+$/, // Less than or equal: <=1.0.0
        /^~\d+\.\d+\.\d+$/, // Tilde: ~1.0.0
        /^\^?\d+\.\d+\.\d+$/, // Caret: ^1.0.0 or 1.0.0
        /^>\d+\.\d+\.\d+$/, // Greater than: >1.0.0
        /^<\d+\.\d+\.\d+$/, // Less than: <1.0.0

        /^\d+\.\d+$/, // Exact version: 1.0
        /^\^?\d+\.\d+$/, // Caret: ^1.0
        /^~\d+\.\d+$/, // Tilde: ~1.0
        /^>\d+\.\d+$/, // Greater than: >1.0
        /^<\d+\.\d+$/, // Less than: <1.0
        /^>=\d+\.\d+$/, // Greater than or equal: >=1.0
        /^<=\d+\.\d+$/, // Less than or equal: <=1.0

        /* eslint-disable security/detect-unsafe-regex -- anchored, non-ambiguous version patterns */
        /^\d+\.\d+(?:dev\d+)?$/,
        /^\d+\.\d+(?:\.\d+)?(?:\.?dev\d+)$/,
        /* eslint-enable security/detect-unsafe-regex */

    ];

    return validPatterns.some(pattern => pattern.test(version));
}

export function validateNamespace(namespace: string): string {
    if (!namespace || namespace.trim() === '') {
        return 'Namespace cannot be empty or just whitespace';
    }

    if (namespace.startsWith('.') || namespace.endsWith('.')) {
        return 'Namespace cannot start or end with a dot';
    }

    if (namespace.includes('..')) {
        return 'Namespace cannot contain empty segments (for example: a..b)';
    }

    const segments = namespace.split('.');
    if (segments.some(segment => segment.trim() === '')) {
        return 'Namespace cannot contain empty segments (for example: a..b)';
    }

    // Lowercase-only pattern: segments must start with lowercase letter or underscore
    const segmentPattern = /^[a-z_][a-z0-9_]*$/;

    for (const segment of segments) {
        if (segment !== segment.toLowerCase()) {
            return 'Each segment of the namespace must be in lowercase';
        }
        if (/^[0-9]/.test(segment)) {
            return 'Each segment of the namespace must not start with a number';
        }
        if (!segmentPattern.test(segment)) {
            return 'Each segment of the namespace must start with a letter or underscore and contain only lowercase letters, numbers, and underscores';
        }
    }

    return '';
}
