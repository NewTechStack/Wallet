import Box from "@material-ui/core/Box";
import Typography from "@material-ui/core/Typography";
import PropTypes from "prop-types";
import React from "react";
import {makeStyles, withStyles} from "@material-ui/core/styles";
import StepConnector from "@material-ui/core/StepConnector";
import clsx from 'clsx';
import TouchAppIcon from '@material-ui/icons/TouchApp';
import BallotIcon from '@material-ui/icons/Ballot';
import {SocialMediaIconsReact} from 'social-media-icons-react';
import IconImage from "../components/Icons/IconImage";
import OdooImg from ".././assets/logos/odoo_2.png"
import AirplayIcon from '@material-ui/icons/Airplay';
import AssignmentIcon from '@material-ui/icons/Assignment';
import PaymentIcon from '@material-ui/icons/Payment';

export const paginationOptions = { rowsPerPageText: 'lignes par page', rangeSeparatorText: 'de', selectAllRowsItem: true, selectAllRowsItemText: 'Total' }
export const tableContextMessage = {singular:"Ligne",plural:"Lignes",message:"sélectionnés"}
export const customTableStyle = {
    header: {
        style: {
            backgroundColor: "#f0f0f0",
        },
    },
}
export function TabPanel(props) {
    const { children, value, index, ...other } = props;

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`full-width-tabpanel-${index}`}
            aria-labelledby={`full-width-tab-${index}`}
            {...other}
        >
            {value === index && (
                <Box p={3}>
                    <Typography>{children}</Typography>
                </Box>
            )}
        </div>
    );
}

TabPanel.propTypes = {
    children: PropTypes.node,
    index: PropTypes.any.isRequired,
    value: PropTypes.any.isRequired,
};

export function a11yProps(index) {
    return {
        id: `full-width-tab-${index}`,
        'aria-controls': `full-width-tabpanel-${index}`,
    };
}

export const ColorlibConnector = withStyles({
    alternativeLabel: {
        top: 22,
    },
    active: {
        '& $line': {
            backgroundImage:
                'linear-gradient( 95deg,rgb(121, 134, 203) 0%,rgb(92, 107, 192) 50%,rgb(57, 73, 171) 100%)',
        },
    },
    completed: {
        '& $line': {
            backgroundImage:
                'linear-gradient( 95deg,rgb(121, 134, 203) 0%,rgb(92, 107, 192) 50%,rgb(57, 73, 171) 100%)',
        },
    },
    line: {
        height: 3,
        border: 0,
        backgroundColor: '#eaeaf0',
        borderRadius: 1,
    },
})(StepConnector);


export function ColorlibStepIcon(props) {
    const classes = useColorlibStepIconStyles();
    const { active, completed } = props;

    const icons = {
        1: <TouchAppIcon />,
        2: <BallotIcon />,
        3: <SocialMediaIconsReact backgroundColor="transparent" icon="wordpress" borderWidth={0} url={false}/>,
        4:<IconImage image={OdooImg} alt="odoo" style={{width:35,height:35}}/>,
        5:<AirplayIcon/>,
        6:<AssignmentIcon/>,
        7:<PaymentIcon/>,
    };

    return (
        <div
            className={clsx(classes.root, {
                [classes.active]: active,
                [classes.completed]: completed,
            })}
        >
            {icons[String(props.icon)]}
        </div>
    );
}

ColorlibStepIcon.propTypes = {
    /**
     * Whether this step is active.
     */
    active: PropTypes.bool,
    /**
     * Mark the step as completed. Is passed to child components.
     */
    completed: PropTypes.bool,
    /**
     * The label displayed in the step icon.
     */
    icon: PropTypes.node,
}

const useColorlibStepIconStyles = makeStyles({
    root: {
        backgroundColor: '#ccc',
        zIndex: 1,
        color: '#fff',
        width: 50,
        height: 50,
        display: 'flex',
        borderRadius: '50%',
        justifyContent: 'center',
        alignItems: 'center',
    },
    active: {
        backgroundImage:
            'linear-gradient( 136deg, rgb(159, 168, 218) 0%, rgb(92, 107, 192) 50%, rgb(57, 73, 171) 100%)',
        boxShadow: '0 4px 10px 0 rgba(0,0,0,.25)',
    },
    completed: {
        backgroundImage:
            'linear-gradient( 136deg, rgb(159, 168, 218) 0%, rgb(92, 107, 192) 50%, rgb(57, 73, 171) 100%)',
    },
});

export const primaryColor="rgb(20, 88, 148)"
export const textTitleColor="rgb(20, 88, 148)"
