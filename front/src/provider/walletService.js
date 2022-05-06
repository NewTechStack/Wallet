const endpoint = process.env.REACT_APP_WALLET_ENDPOINT;

let WalletService ={

    loadHeaders() {
        let headers = new Headers();
        headers.append('Content-Type', 'application/json');
        headers.append("Accept", '*/*');
        return headers;
    },

    loadHeadersToken(token) {
        let headers = new Headers();
        headers.append('Content-Type', 'application/json');
        headers.append("Accept", '*/*');
        headers.append("usrtoken", token);
        return headers;
    },

    chain(usrtoken){
        return fetch(endpoint+'/chain', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    add_wallet(usrtoken,data){
        return fetch(endpoint+'/wallet', {
            method: 'POST',
            headers:this.loadHeadersToken(usrtoken),
            body:JSON.stringify(data)
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallets(usrtoken){
        return fetch(endpoint+'/wallets', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallet_balance(usrtoken,wallet_id,){
        return fetch(endpoint+'/wallet/' + wallet_id + '/balance', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    get_wallet_contract_balance(usrtoken,wallet_id,contract_id){
        return fetch(endpoint+'/wallet/' + wallet_id + '/contract/' + contract_id + '/balance', {
            method: 'GET',
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContracts(wallet_adrs){
        return fetch(endpoint+'/wallet/' + wallet_adrs + '/contracts', {
            method: 'GET',
            headers:this.loadHeaders(),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

    getContractName(contract_id,data,usrtoken){
        return fetch(endpoint+'/contract/' + contract_id + '/name', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },


    getContractSymbol(contract_id,data,usrtoken){
        return fetch(endpoint+'/contract/' + contract_id + '/symbol', {
            method: 'POST',
            body:JSON.stringify(data),
            headers:this.loadHeadersToken(usrtoken),
        }).then(response => response.json()).catch(error => {
            console.log(error);
        });
    },

}


export default WalletService;
