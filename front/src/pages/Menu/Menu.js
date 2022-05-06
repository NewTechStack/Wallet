import React from "react";
import './menu.css'
import {Link} from "react-router-dom";
import Drawer from "@material-ui/core/Drawer";
import {textTitleColor} from "../../constants/defaultValues";
import rocket_logo from "../../assets/logos/rocket.jpeg"

export default class Menu extends React.Component{


    state={
        active_item:this.props.active_item
    }

    componentDidMount() {
        console.log(this.props.active_item)
        let arrow = document.querySelectorAll(".arrow");
        for (var i = 0; i < arrow.length; i++) {
            arrow[i].addEventListener("click", (e)=>{
                console.log("CLICKED")
                let arrowParent = e.target.parentElement.parentElement;
                arrowParent.classList.toggle("showMenu");
            });
        }
    }


    render() {

        if(this.props.openDrawerMenu === true){
            let arrow = document.querySelectorAll(".arrow");
            for (var i = 0; i < arrow.length; i++) {
                arrow[i].addEventListener("click", (e)=>{
                    console.log("CLICKED")
                    let arrowParent = e.target.parentElement.parentElement;
                    arrowParent.classList.toggle("showMenu");
                });
            }
        }

        return(
            <>


                    <div className="sidebar close"
                         style={{backgroundColor:"#fff",visibility:this.props.isMobile === false ? "unset" : "hidden"}}
                    >
                        <div className="logo-details">
                            {
                                this.props.show_logo === true &&
                                <img alt="" src={rocket_logo} style={{width:50,height:40,objectFit:"contain",marginLeft:12,marginRight:10}}/>
                            }
                            <span className="logo_name" style={{color:this.props.top_title_color}}>{this.props.top_title}</span>
                        </div>
                        <ul className="nav-links">
                            {
                                this.props.items.map((item,key) => (
                                    <li key={key} style={{backgroundColor: this.state.active_item === key+1 ? "#fff" :"inherit",boxShadow:this.state.active_item === key+1 ? "0 5px 15px 0 rgb(0 0 0 / 10%)" : "none" }}
                                        onClick={() => {this.setState({active_item:key+1})}}
                                    >
                                        {
                                            item.childrens && item.childrens.length > 0 ?
                                                <div className="iocn-link">
                                                    <Link style={{cursor:"pointer"}} to={item.route}>
                                                        <i className={item.icon} style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.icons_color}}/>
                                                        <span className="link_name" style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.titles_color}}>{item.title}</span>
                                                    </Link>
                                                    <i className='bx bxs-chevron-down arrow' style={{color:this.state.active_item === key+1 ? textTitleColor :this.props.icons_color}}/>
                                                </div> :
                                                <Link style={{cursor:"pointer"}} to={item.route}>
                                                    <i className={item.icon} style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.icons_color}}/>
                                                    <span className="link_name" style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.titles_color}}>{item.title}</span>
                                                </Link>
                                        }

                                        <ul className={item.childrens && item.childrens.length > 0 ? "sub-menu" : "sub-menu blank"}>
                                            <li>
                                                <Link className="link_name" style={{color:textTitleColor,cursor:"pointer",fontSize:"1.05rem"}}
                                                      to={item.route}>{item.title}</Link>
                                            </li>
                                            {
                                                (item.childrens || []).map((child,k) => (
                                                    <li style={{cursor:"pointer",margin:5}} key={k}>
                                                        <Link style={{fontSize:"1.05rem"}} to={child.route}>{child.title}</Link>
                                                    </li>
                                                ))
                                            }
                                        </ul>
                                    </li>
                                ))
                            }
                            {
                                this.props.show_active_user === true &&
                                <li>
                                    <div className="profile-details">
                                        <div className="profile-content">
                                            <img src={this.props.active_user_img} alt="profileImg"/>
                                        </div>
                                        <div className="name-job">
                                            <div className="profile_name">{this.props.active_user_name}</div>
                                            <div className="job">{this.props.active_user_details}</div>
                                        </div>
                                        <i className='bx bx-log-out'/>
                                    </div>
                                </li>
                            }

                        </ul>
                    </div>


                <Drawer anchor={"left"} open={this.props.openDrawerMenu} onClose={() => {
                    this.props.setOpenDrawerMenu()
                }}
                >
                        <div className="sidebar"
                             style={{backgroundColor:"#fff"}}
                        >
                            <div className="logo-details">
                                {
                                    this.props.show_logo === true &&
                                    <i className={this.props.ilogo}/>
                                }
                                <span className="logo_name" style={{color:this.props.top_title_color}}>{this.props.top_title}</span>
                            </div>
                            <ul className="nav-links">
                                {
                                    this.props.items.map((item,key) => (
                                        <li key={key} style={{backgroundColor: this.state.active_item === key+1 ? "#fff" :"inherit",boxShadow:this.state.active_item === key+1 ? "0 5px 15px 0 rgb(0 0 0 / 10%)" : "none" }}
                                            onClick={() => {this.setState({active_item:key+1})}}
                                        >
                                            {
                                                item.childrens && item.childrens.length > 0 ?
                                                    <div className="iocn-link">
                                                        <Link style={{cursor:"pointer"}} to={item.route}>
                                                            <i className={item.icon} style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.icons_color}}/>
                                                            <span className="link_name" style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.titles_color}}>{item.title}</span>
                                                        </Link>
                                                        <i className='bx bxs-chevron-down arrow' style={{color:this.state.active_item === key+1 ? textTitleColor :this.props.icons_color}}/>
                                                    </div> :
                                                    <Link style={{cursor:"pointer"}} to={item.route}>
                                                        <i className={item.icon} style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.icons_color}}/>
                                                        <span className="link_name" style={{color:this.state.active_item === key+1 ? textTitleColor : this.props.titles_color}}>{item.title}</span>
                                                    </Link>
                                            }

                                            <ul className={item.childrens && item.childrens.length > 0 ? "sub-menu" : "sub-menu blank"}>
                                                <li>
                                                    <Link className="link_name" style={{color:"#000",cursor:"pointer",fontSize:"1.05rem"}}
                                                          to={item.route}>{item.title}</Link>
                                                </li>
                                                {
                                                    (item.childrens || []).map((child,k) => (
                                                        <li style={{cursor:"pointer",margin:5}} key={k}>
                                                            <Link style={{fontSize:"1.05rem"}} to={child.route}>{child.title}</Link>
                                                        </li>
                                                    ))
                                                }
                                            </ul>
                                        </li>
                                    ))
                                }
                                {
                                    this.props.show_active_user === true &&
                                    <li>
                                        <div className="profile-details">
                                            <div className="profile-content">
                                                <img src={this.props.active_user_img} alt="profileImg"/>
                                            </div>
                                            <div className="name-job">
                                                <div className="profile_name">{this.props.active_user_name}</div>
                                                <div className="job">{this.props.active_user_details}</div>
                                            </div>
                                            <i className='bx bx-log-out'/>
                                        </div>
                                    </li>
                                }

                            </ul>
                        </div>

                </Drawer>

            </>
        )

    }





}
