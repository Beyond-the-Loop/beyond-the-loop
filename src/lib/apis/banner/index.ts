import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

export const getBannerMessage = async () => {
    let notification = null;
    try{
        const response = await fetch(`${WEBUI_BASE_URL}/banner/message`);
    
        if (response.ok) {
            const data = await response.json();
            notification = data;

            return notification;
        }
    } catch (err) 
    {      
        console.error('Keine Bannermeldung gefunden!', err);    
        return null;
    }
};