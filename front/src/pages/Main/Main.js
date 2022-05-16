import React, {useEffect} from "react";
import Menu from "../Menu/Menu";
import profile_img from "../../assets/images/profile.jpg"
import Divider from '@material-ui/core/Divider';
import MenuItem from '@material-ui/core/MenuItem';
import MuiMenu from '@material-ui/core/Menu';
import organisation from "../../assets/images/icons/organisation.svg"
import team from "../../assets/images/icons/team.svg"
import bill from "../../assets/images/icons/bill.svg"
import lifeguard from "../../assets/images/icons/lifeguard.svg"
import user from "../../assets/images/icons/user.svg"
import personalInformation from "../../assets/images/icons/personal-information.svg"
import turnOff from "../../assets/images/icons/turn-off.svg"
import Avatar from "@atlaskit/avatar";
import moment from "moment";
import {
    Switch,
    Route, Redirect
} from 'react-router-dom';
import Login from "../auth/login";
import MyAccount from "./MyAccount";
import Lozenge from "@atlaskit/lozenge";
import DropdownMenu, { DropdownItem, DropdownItemGroup } from '@atlaskit/dropdown-menu';
import ApartmentIcon from '@material-ui/icons/Apartment';
import GroupIcon from '@material-ui/icons/Group';
import ReceiptIcon from '@material-ui/icons/Receipt';
import HelpIcon from '@material-ui/icons/Help';
import AccountCircleIcon from '@material-ui/icons/AccountCircle';
import StorageIcon from '@material-ui/icons/Storage';
import LockIcon from '@material-ui/icons/Lock';
import user_icon from "../../assets/images/icons/user.png"
import {primaryColor, textTitleColor} from "../../constants/defaultValues";
import { useMediaQuery } from 'react-responsive'
import DashMain from "./Dashboard/Main"

const menu_items = [
    /*{
        title: "Mon compte",
        icon: "bx bx-grid-alt",
        route: "/admin/myaccount"
    },
    {
        title: "Administration",
        icon: "bx bx-data",
        route: "/admin/administration",
    },
    {
        title: "Gestion des NDD",
        icon: "bx bx-cloud",
        route: "/admin/ndd"
    },*/
    {
        title: "Tableau de bord",
        icon: "bx bx-shopping-bag",
        route: "/main/dashboard"
    },
    /*{
        title: "Mes transactions",
        icon: "bx bx-dock-top",
        route: "/main/transactions"
    }*/
]


export default function Main(props) {

    const [toggle_menu, setToggle_menu] = React.useState(false);
    const [openDrawerMenu, setOpenDrawerMenu] = React.useState(false);
    const [currentPage, setCurrentPage] = React.useState("");


    const isMobile = useMediaQuery({ query: '(max-width: 1000px)' })
    const isBigScreen = useMediaQuery({ query: '(min-width: 1000px)' })





    const verifSession = () => {
        return !(localStorage.getItem("usrtoken") === null || localStorage.getItem("usrtoken") === undefined || parseInt(localStorage.getItem("exp")) < moment().unix());
    }



    const username = localStorage.getItem("username") ? localStorage.getItem("username") : ""

    return (
        <>
                <Menu background_color={primaryColor} ilogo="bx bx-wallet" top_title="" top_title_color="#000"
                      show_logo={false}
                      show_active_user={false}
                      active_user_name="Babba Amine" active_user_details="Web developper" active_user_img={profile_img}
                      icons_color={textTitleColor} titles_color={textTitleColor}
                      items={menu_items}
                      on_logout={() => {
                      }}
                      active_item={
                          props.history.location.pathname === "/main/myaccount" ? 1 :
                              props.history.location.pathname === "/main/dashboard" ? 2 :
                                  props.history.location.pathname === "/main/transactions" ? 3 : 1

                      }
                      openDrawerMenu={openDrawerMenu}
                      setOpenDrawerMenu={() => {
                          setOpenDrawerMenu(!openDrawerMenu)
                      }}
                      isMobile={isMobile}
                />




                <section className="home-section"
                         style={{left: isBigScreen ? (toggle_menu === false ? 78 : 240) : 0,
                             width:"calc(100% - " + (isBigScreen ?  toggle_menu === false ? 78 : 240 : 0).toString() + "px)"
                         }}
                >
                    <div className="home-content">
                        <i className='bx bx-menu' style={{color:textTitleColor}}
                           onClick={(event => {
                               if (isBigScreen) {
                                   let sidebar = document.querySelector(".sidebar");
                                   sidebar.classList.toggle("close");
                                   setToggle_menu(!toggle_menu)
                               } else if (isMobile) {
                                   setOpenDrawerMenu(!openDrawerMenu)
                               }
                           })}
                        />
                        <span className="text" style={{color:textTitleColor}}>{currentPage}</span>

                        <div style={{position: "fixed", right: 5,display:"grid"}} className="user-avatar-container">

                            <DropdownMenu
                                trigger={({ triggerRef, ...props }) => (
                                    <div
                                        {...props}
                                        ref={triggerRef}
                                        style={{cursor:"pointer",display:"flex"}}
                                    >
                                        {/*<Avatar  size="small" src={user_icon} style={{margin:2,marginTop:3}}/>*/}
                                        <AccountCircleIcon fontSize="default" color="primary" style={{margin:2,marginTop:3}}/>
                                        <h6 style={{alignSelf:"center",fontWeight:"bold",marginTop:6,color:"rgb(20, 88, 148)"}}>&nbsp;{username}</h6>
                                        {/*<Lozenge appearance="removed">
                                            admin
                                        </Lozenge>*/}
                                    </div>
                                )}
                            >
                                <DropdownItemGroup>
                                    {/*<DropdownItem elemBefore={<ApartmentIcon fontSize="medium" color="primary" />}>Organisation</DropdownItem>
                                    <DropdownItem elemBefore={<GroupIcon fontSize="medium" color="primary" />}>Members</DropdownItem>
                                    <DropdownItem elemBefore={<ReceiptIcon fontSize="medium" color="primary" />}>Facturation</DropdownItem>
                                    <DropdownItem elemBefore={<HelpIcon fontSize="medium" color="primary" />}>Niveau de support</DropdownItem>*/}
                                    <DropdownItem elemBefore={<AccountCircleIcon fontSize="medium" color="primary" />}
                                                  onClick={() => {
                                                      props.history.push("/main/myaccount")
                                                  }}
                                    >
                                        Mon profil
                                    </DropdownItem>
                                    {/*<DropdownItem elemBefore={<StorageIcon fontSize="medium" color="primary" />}>Mes données</DropdownItem>*/}
                                    <DropdownItem elemBefore={<LockIcon fontSize="medium" color="error" />}
                                                  onClick={(e => {
                                                      localStorage.removeItem("usrtoken")
                                                      localStorage.removeItem("username")
                                                      localStorage.removeItem("email")
                                                      localStorage.removeItem("exp")
                                                      localStorage.removeItem("id")
                                                      window.location.reload()
                                                  })}
                                    >Déconnexion</DropdownItem>
                                </DropdownItemGroup>
                            </DropdownMenu>





                        </div>
                    </div>

                    <div style={{paddingTop: 30}}>

                        <Switch>

                            {
                                verifSession() === false &&
                                <Redirect from={"/main"} to={"/login"}/>
                            }

                            <Redirect exact from={"/main"} to="/main/dashboard"/>
                            <Route path={'/main/myaccount'}>
                                <MyAccount setCurrentPage={() => setCurrentPage("Mon compte")}/>
                            </Route>
                            <Route path={'/main/dashboard'}>
                                <DashMain  setCurrentPage={() => setCurrentPage("")}/>

                            </Route>

                            <Route exact path="/login" component={Login}/>

                        </Switch>


                    </div>
                </section>


            </>
    )


}

