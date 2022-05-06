import React, {useEffect, useState} from "react";
import Tabs from '@material-ui/core/Tabs';
import Tab from '@material-ui/core/Tab';
import SwipeableViews from 'react-swipeable-views';
import {TabPanel, a11yProps} from "../../constants/defaultValues";
import Textfield from '@atlaskit/textfield';

export default function MyAccount(props) {



    const [value, setValue] = React.useState(0);
    const [fname, setFname] = useState(localStorage.getItem("username") || '');
    const [email, setEmail] = useState(localStorage.getItem("email") || '');
    const [phone, setPhone] = useState('');
    const [adress, setAdress] = useState('');

    useEffect(() => {
        props.setCurrentPage()
    }, []);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    const handleChangeIndex = (index) => {
        setValue(index);
    };



    return (
        <>
            <div className="container-fluid" style={{marginTop: 60, marginLeft: 15}}>


                <Tabs
                    value={value}
                    onChange={handleChange}
                    indicatorColor="primary"
                    textColor="primary"
                    aria-label="full width tabs example"
                >
                    <Tab label="Info générales" {...a11yProps(0)} />
                    {/*<Tab label="Sécurité" {...a11yProps(1)} />
                    <Tab label="Activités" {...a11yProps(2)} />*/}
                </Tabs>

                <SwipeableViews
                    axis={'x'}
                    index={value}
                    onChangeIndex={handleChangeIndex}
                >
                    <TabPanel value={value} index={0} dir={'x'}>
                        <>
                            <div className="row mt-3">
                                <div className="col-lg-6">
                                    <label>Pseudo</label>
                                    <Textfield value={fname}
                                               onChange={event => setFname(event.target.value)}
                                               placeholder="Nom & Prénom"
                                    />
                                </div>

                            </div>
                            <div className="row mt-3">
                                <div className="col-lg-6">
                                    <label>Email</label>
                                    <Textfield value={email}
                                               onChange={event => setEmail(event.target.value)}
                                               placeholder="Email"
                                    />
                                </div>
                            </div>
                            {/*<div className="row mt-3">
                                <div className="col-lg-6">
                                    <label>Téléphone</label>
                                    <Textfield value={phone}
                                               onChange={event => setPhone(event.target.value)}
                                               placeholder="Téléphone"
                                    />
                                </div>
                            </div>
                            <div className="row mt-3">
                                <div className="col-lg-6">
                                    <label>Adresse</label>
                                    <Textfield value={adress}
                                               onChange={event => setAdress(event.target.value)}
                                               placeholder="Adresse"
                                    />
                                </div>
                            </div>*/}
                        </>
                    </TabPanel>
                    {/*<TabPanel value={value} index={1} dir={'x'}>
                    </TabPanel>
                    <TabPanel value={value} index={2} dir={'x'}>
                    </TabPanel>*/}
                </SwipeableViews>

            </div>
        </>
    )
}
