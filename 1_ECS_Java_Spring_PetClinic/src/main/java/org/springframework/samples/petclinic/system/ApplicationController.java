package org.springframework.samples.petclinic.system;


import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.samples.petclinic.model.Pet;
import org.springframework.samples.petclinic.model.Visit;
import org.springframework.samples.petclinic.owner.OwnerRepository;
import org.springframework.samples.petclinic.pet.PetRepository;
import org.springframework.web.bind.annotation.*;

import javax.inject.Inject;
import java.util.ArrayList;
import java.util.List;

@RestController
class ApplicationController {

    @RequestMapping("/")
    public String home() {
        return "Welcome to PetClinic";
    }

    @Inject
    private PetRepository pets;
    @Inject
    private OwnerRepository owners;
    private static final Logger logger = LoggerFactory.getLogger(ApplicationController.class);

}
