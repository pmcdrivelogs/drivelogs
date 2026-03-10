document.addEventListener('DOMContentLoaded', function(){
  const vehicleSelect = document.querySelector('select[name="vehicle_id"]');
  const regInput = document.querySelector('input[name="registration_no"]');
  if(vehicleSelect && regInput){
    vehicleSelect.addEventListener('change', function(){
      const opt = this.options[this.selectedIndex];
      const reg = opt.getAttribute('data-reg') || '';
      regInput.value = reg;
    });
  }
});
