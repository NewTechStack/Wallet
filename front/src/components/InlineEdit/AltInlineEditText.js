import React, { useState } from 'react';

import { gridSize as getGridSize } from '@atlaskit/theme/constants';

import { InlineEditableTextfield } from '@atlaskit/inline-edit';

const gridSize = getGridSize();

const AltInlineEditText = (props) => {


    const validate = (value: string) => {
        if (value.length <= 3) {
            return 'Veuillez saisir une valeur supérieure à 3 caractères';
        }
        return undefined;
    };

    return (
        <div
            style={{
                padding: `${gridSize}px ${gridSize}px ${gridSize * 6}px`,
            }}
        >
            <InlineEditableTextfield
                defaultValue={props.defaultValue || ""}
                label={props.label || ""}
                onConfirm={(value) => props.setValue(value)}
                placeholder={props.placeholder || ""}
                validate={validate}
                /*startWithEditViewOpen={true}*/
            />
        </div>
    );
};
export default AltInlineEditText;
