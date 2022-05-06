let verifForms = {

    verif_inpuText:function(text) {
        return text === '' || text.trim() === '';
    },

    verif_Number:function(phone){
        return this.verif_inpuText(phone) || isNaN(phone) || parseInt(phone) < 0;
    },
    verif_Password:function(pwd){
        let lowerCaseLetters = /[a-z]/g;
        let upperCaseLetters = /[A-Z]/g;
        let numbers = /[0-9]/g;
        return this.verif_inpuText(pwd) || !pwd.match(lowerCaseLetters) || !pwd.match(upperCaseLetters) || !pwd.match(numbers) || pwd.length < 6 ;
    },
    verif_match(pwd1,pwd2) {
        return ((pwd1 === '' && pwd2 === '') || (pwd1 !== pwd2));
    },
    verif_Email:function (email) {
        return this.verif_inpuText(email) || !(/^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,9})+$/.test(email));
    },

    verif_ndd(ndd){
        //return this.verif_inpuText(ndd) || !(/^(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\.[a-zA-Z]{2,3})$/.test(ndd));
        const ndd_regex = new RegExp('^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9](?:\\.[a-zA-Z]{2,})+$')
        return this.verif_inpuText(ndd) || !ndd_regex.test(ndd)
    }
};

export default verifForms
